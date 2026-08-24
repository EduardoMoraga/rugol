"""Después de un corte, Rugol tiene que volver solo y decir qué encontró.

Estos tests simulan el escenario real: había corridas activas, se cortó la
luz, el proceso vuelve a arrancar.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select, text

from core.db import async_session_factory, engine, init_db
from core.db.models import Agent, Project, Run
from core.resilience import (
    INTERRUPTED_MESSAGE,
    RecoveryReport,
    backup_database,
    integrity_check,
    last_report,
    recover_interrupted_runs,
    set_last_report,
    startup_recovery,
)


@pytest.fixture
async def db():
    await init_db()
    yield
    # Limpieza: sólo lo que crearon estos tests.
    async with async_session_factory() as s:
        for r in (await s.execute(select(Run).where(Run.prompt.like("test-resilience%")))).scalars():
            await s.delete(r)
        for a in (await s.execute(select(Agent).where(Agent.name.like("resil-%")))).scalars():
            await s.delete(a)
        await s.commit()


async def _make_agent(session, name: str, status: str = "idle") -> Agent:
    project = (await session.execute(select(Project).where(Project.slug == "workspace"))).scalar_one()
    agent = Agent(name=name, model="claude-sonnet-5", description="fixture",
                  body="fixture", source_path=f"/tmp/{name}.md", body_hash="deadbeef",
                  status=status, project_id=project.id)
    session.add(agent)
    await session.flush()
    return agent


# ── Pragmas ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sqlite_runs_in_wal_mode():
    """WAL es lo que hace que un corte deje una base recuperable."""
    async with engine.connect() as conn:
        mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
        fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
    assert str(mode).lower() == "wal", f"journal_mode={mode}"
    assert int(fk) == 1, "el esquema usa ON DELETE CASCADE; sin foreign_keys=ON se ignora"


@pytest.mark.asyncio
async def test_integrity_check_reports_ok():
    assert await integrity_check() == "ok"


# ── Recuperación de corridas ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_interrupted_runs_are_closed_not_left_running(db):
    async with async_session_factory() as s:
        agent = await _make_agent(s, "resil-a", status="running")
        s.add_all([
            Run(agent_id=agent.id, source="schedule", prompt="test-resilience running",
                status="running", started_at=dt.datetime.now(dt.UTC)),
            Run(agent_id=agent.id, source="telegram", prompt="test-resilience queued",
                status="queued", started_at=dt.datetime.now(dt.UTC)),
        ])
        await s.commit()

    runs, agents = await recover_interrupted_runs()
    assert runs >= 2
    assert agents >= 1

    async with async_session_factory() as s:
        rows = (await s.execute(
            select(Run).where(Run.prompt.like("test-resilience%"))
        )).scalars().all()
        assert rows, "los runs de prueba deberían existir"
        for r in rows:
            assert r.status == "interrupted", f"quedó en {r.status}"
            assert r.ended_at is not None, "una corrida cerrada necesita ended_at"
            assert r.error_message == INTERRUPTED_MESSAGE

        agent = (await s.execute(select(Agent).where(Agent.name == "resil-a"))).scalar_one()
        assert agent.status == "idle", "el agente tiene que volver a idle"


@pytest.mark.asyncio
async def test_interrupted_is_not_failed(db):
    """`failed` alimenta el trigger del bucle self-improving; una interrupción
    no es un fracaso del agente y no debe contar como tal."""
    async with async_session_factory() as s:
        agent = await _make_agent(s, "resil-b")
        s.add(Run(agent_id=agent.id, source="api", prompt="test-resilience x",
                  status="running", started_at=dt.datetime.now(dt.UTC)))
        await s.commit()

    await recover_interrupted_runs()

    async with async_session_factory() as s:
        r = (await s.execute(
            select(Run).where(Run.prompt == "test-resilience x")
        )).scalar_one()
        assert r.status == "interrupted"
        assert r.status != "failed"


@pytest.mark.asyncio
async def test_completed_runs_are_left_alone(db):
    async with async_session_factory() as s:
        agent = await _make_agent(s, "resil-c")
        s.add(Run(agent_id=agent.id, source="api", prompt="test-resilience done",
                  status="completed", started_at=dt.datetime.now(dt.UTC),
                  ended_at=dt.datetime.now(dt.UTC), final_text="listo"))
        await s.commit()

    await recover_interrupted_runs()

    async with async_session_factory() as s:
        r = (await s.execute(
            select(Run).where(Run.prompt == "test-resilience done")
        )).scalar_one()
        assert r.status == "completed"
        assert r.error_message is None


@pytest.mark.asyncio
async def test_recovery_is_idempotent(db):
    """Arrancar dos veces no debe reportar trabajo la segunda."""
    async with async_session_factory() as s:
        agent = await _make_agent(s, "resil-d", status="running")
        s.add(Run(agent_id=agent.id, source="api", prompt="test-resilience idem",
                  status="running", started_at=dt.datetime.now(dt.UTC)))
        await s.commit()

    first = await recover_interrupted_runs()
    second = await recover_interrupted_runs()
    assert first[0] >= 1
    assert second == (0, 0), f"la segunda pasada no debería tocar nada: {second}"


# ── Respaldo ─────────────────────────────────────────────────────────────────
def test_backup_rotates_and_keeps_the_newest(tmp_path, monkeypatch):
    db_file = tmp_path / "rugol.db"
    db_file.write_bytes(b"SQLite format 3\x00" + b"x" * 200)
    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")

    from core.config import get_settings
    get_settings.cache_clear()
    try:
        # Cuatro respaldos previos, del más viejo al más nuevo.
        backups = tmp_path / "backups"
        backups.mkdir()
        for stamp in ("20260101-000001", "20260102-000001", "20260103-000001", "20260104-000001"):
            (backups / f"rugol-{stamp}.db").write_bytes(b"viejo")

        fresh = backup_database(keep=3)
        assert fresh, "debería haber creado un respaldo nuevo"

        kept = sorted(p.name for p in backups.glob("rugol-*.db"))
        assert len(kept) == 3, f"debería conservar 3, hay {len(kept)}: {kept}"
        assert fresh in kept, "el más nuevo tiene que sobrevivir a la rotación"
        assert "rugol-20260101-000001.db" not in kept, "el más viejo tiene que irse"
    finally:
        get_settings.cache_clear()


def test_backup_is_a_noop_without_sqlite(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@host/db")
    from core.config import get_settings
    get_settings.cache_clear()
    try:
        assert backup_database() == ""
    finally:
        get_settings.cache_clear()


# ── Reporte ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_startup_recovery_reports_and_never_raises(db):
    report = await startup_recovery(backup=False)
    assert isinstance(report, RecoveryReport)
    d = report.as_dict()
    assert set(d) >= {"interrupted_runs", "reset_agents", "integrity", "clean"}
    assert d["integrity"] == "ok"

    set_last_report(report)
    assert last_report() is report, "el reporte tiene que quedar disponible para /api/health/full"


@pytest.mark.asyncio
async def test_startup_recovery_survives_a_broken_stage(monkeypatch, db):
    """Un Rugol que levanta con advertencia sirve; uno que no levanta, no."""
    async def boom():
        raise RuntimeError("disco lleno")

    monkeypatch.setattr("core.resilience.recover_interrupted_runs", boom)
    report = await startup_recovery(backup=False)
    assert "la recuperación de corridas falló" in report.notes
    assert report.interrupted_runs == 0


def test_report_flags_dirty_state():
    assert RecoveryReport().clean
    assert not RecoveryReport(interrupted_runs=2).clean
    assert not RecoveryReport(integrity="malformed database").clean


# ── Contrato backend ↔ dashboard ─────────────────────────────────────────────
def test_terminal_statuses_match_the_dashboard():
    """Los dos lados tienen que conocer los mismos estados finales.

    Regresión concreta: el backend agregó `interrupted` y el dashboard no se
    enteró. El chat consultaba la corrida cada pocos segundos esperando un
    estado que nunca iba a llegar — refrescaba para siempre.
    """
    import re

    from core.config import REPO_ROOT
    from core.db.models import TERMINAL_RUN_STATUSES

    ts = (REPO_ROOT / "dashboard/src/lib/api.ts").read_text(encoding="utf-8")
    m = re.search(r"TERMINAL_RUN_STATUSES\s*=\s*\[(.*?)\]", ts, re.S)
    assert m, "no encontré TERMINAL_RUN_STATUSES en dashboard/src/lib/api.ts"
    front = set(re.findall(r'"([a-z]+)"', m.group(1)))

    assert front == set(TERMINAL_RUN_STATUSES), (
        f"backend={sorted(TERMINAL_RUN_STATUSES)} vs dashboard={sorted(front)} — "
        "agregá el estado en los dos lados"
    )


def test_interrupted_is_a_terminal_status():
    from core.db.models import TERMINAL_RUN_STATUSES
    assert "interrupted" in TERMINAL_RUN_STATUSES
    assert "running" not in TERMINAL_RUN_STATUSES
    assert "queued" not in TERMINAL_RUN_STATUSES


# ── Lo que los agentes aprendieron no puede vivir en el código ────────────────
# El defecto: `agent-memory/` y `agent-soul/` vivían DENTRO del directorio de la
# app. Una reinstalación borra ese directorio. O sea: el corazón del producto
# —las memorias y la evolución de los prompts— guardado en el único lugar que la
# instalación destruye.

def test_memories_live_outside_the_app_directory(tmp_path, monkeypatch):
    import core.memory.store as store
    from core.config import REPO_ROOT

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    target = store.memory_dir("un-agente")

    assert str(target).startswith(str(tmp_path)), target
    assert REPO_ROOT not in target.parents, (
        "las memorias no pueden vivir dentro del directorio de la app: "
        "reinstalar las borraría"
    )


def test_soul_archive_lives_outside_the_app_directory(tmp_path, monkeypatch):
    from core.config import REPO_ROOT
    from core.soul.evolution.archive import archive_dir

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    target = archive_dir("un-agente")

    assert str(target).startswith(str(tmp_path)), target
    assert REPO_ROOT not in target.parents


def test_legacy_state_dirs_are_adopted_without_clobbering(tmp_path, monkeypatch):
    """Al actualizar, lo que quedó en el código se copia — sin pisar lo nuevo."""
    from core.config import REPO_ROOT, adopt_legacy_state_dirs

    legacy = REPO_ROOT / "agent-memory"
    legacy.mkdir(parents=True, exist_ok=True)
    probe = legacy / "agente-de-prueba-adopcion"
    probe.mkdir(exist_ok=True)
    (probe / "MEMORY.md").write_text("- memoria vieja\n", encoding="utf-8")

    try:
        monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
        assert "agent-memory" in adopt_legacy_state_dirs(("agent-memory",))
        adoptada = tmp_path / "agent-memory" / "agente-de-prueba-adopcion" / "MEMORY.md"
        assert adoptada.read_text() == "- memoria vieja\n"
        assert probe.exists(), "el original queda como respaldo"

        # Segunda pasada: no pisa lo que ya está.
        adoptada.write_text("- memoria nueva\n", encoding="utf-8")
        adopt_legacy_state_dirs(("agent-memory",))
        assert adoptada.read_text() == "- memoria nueva\n"
    finally:
        import shutil
        shutil.rmtree(probe, ignore_errors=True)
