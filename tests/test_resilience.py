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


# ── El launcher no puede dejar procesos agarrados al puerto ───────────────────
# Bug medido en la instalación real: `rugol down` mata por archivo de pid. Si
# ese archivo quedó desactualizado (reinicio a medias, kill -9), el proceso viejo
# sobrevive con el puerto. `up` lanza uno nuevo que no puede bindear y muere, el
# archivo apunta a un muerto, y el usuario sigue viendo el dashboard VIEJO —
# código viejo — sin que nada avise. Pasó: puerto 3000 en el pid 80112 mientras
# dashboard.pid decía 86051.

def _launcher() -> str:
    from core.config import REPO_ROOT
    return (REPO_ROOT / "cli" / "rugol").read_text(encoding="utf-8")


def test_the_launcher_adopts_a_healthy_process_on_its_port():
    src = _launcher()
    assert "_pid_on_port" in src and "_is_ours" in src
    # Adopción: si el puerto lo tiene un proceso nuestro y responde, se escribe
    # su pid en vez de lanzar un duplicado.
    assert 'echo "$held" > "$RUN_DIR/core.pid"' in src
    assert 'echo "$held" > "$RUN_DIR/dashboard.pid"' in src


def test_down_frees_the_port_even_with_a_stale_pid_file():
    src = _launcher()
    down = src[src.index("cmd_down() {"):src.index("cmd_restart()")]
    assert "_free_port_if_ours" in down, (
        "sin esto, el próximo `up` lanza un duplicado que no puede bindear"
    )


def test_it_never_kills_a_foreign_process():
    """Matar algo ajeno que casualmente usa el puerto sería peor que no
    arrancar."""
    src = _launcher()
    fn = src[src.index("_free_port_if_ours() {"):]
    fn = fn[:fn.index("\n}\n") + 3]
    assert "_is_ours" in fn
    assert "no lo toco" in fn, "hay que avisar y abstenerse, no matar a ciegas"


def test_the_supervisor_checks_health_not_just_the_pid():
    """Un core colgado —vivo pero sin responder— es el caso que un chequeo por
    pid no ve, y justo el que deja el asistente muerto sin que se note."""
    src = _launcher()
    sup = src[src.index("cmd_supervise() {"):]
    sup = sup[:sup.index("\n}\n") + 3]
    assert "/api/health" in sup, "el supervisor tiene que mirar salud"
    assert "tolerancia" in sup, "no debe reaccionar a un pico transitorio"
    assert "core_fails" in sup


# ── Horarios: no alcanza con disparar, hay que poder verlo ────────────────────
# `Schedule.last_run_at` no se escribía en NINGÚN lado. La pantalla de Horarios
# decía "nunca corrió" incluso para uno que llevaba meses disparando: no había
# forma de saber si el briefing de la mañana se había ejecutado.

def test_firing_a_schedule_records_it():
    import inspect

    from core.scheduler import scheduler as sched

    fuente = inspect.getsource(sched._fire_schedule)
    assert "last_run_at" in fuente, (
        "sin esto la pantalla de Horarios dice 'nunca corrió' para siempre"
    )
    # Y no puede tumbar la corrida: anotar el disparo es contabilidad.
    assert "except Exception" in fuente


def test_the_schedule_dto_says_how_it_went_not_just_when():
    from core.api.schedules import ScheduleDTO

    campos = ScheduleDTO.model_fields
    for campo in ("last_run_at", "last_status", "last_run_id"):
        assert campo in campos, f"falta {campo}"


# ── La vista de flota no puede mentir ────────────────────────────────────────
# Con MAX_CONCURRENT_RUNS=3 y cinco pedidos, las cinco corridas nacían
# "running": el dashboard mostraba cinco agentes trabajando cuando tres estaban
# esperando turno.

def test_runs_start_queued_and_become_running_when_they_get_a_slot():
    import inspect

    from core.runner import orchestrator as orch

    enqueue = inspect.getsource(orch.RuntimeOrchestrator.enqueue)
    assert 'status="queued"' in enqueue
    assert 'status="running"' not in enqueue

    execute = inspect.getsource(orch.RuntimeOrchestrator._execute)
    assert "async with self._sem:" in execute
    # La transición va DESPUÉS de conseguir cupo, no antes.
    assert execute.index("async with self._sem:") < execute.index("_mark_running")


@pytest.mark.asyncio
async def test_queued_runs_are_recovered_after_a_crash(tmp_path, monkeypatch):
    """Una corrida que se quedó esperando cupo cuando se cortó la luz también
    tiene que cerrarse: si no, queda en cola para siempre."""
    from core.db.models import TERMINAL_RUN_STATUSES

    assert "queued" not in TERMINAL_RUN_STATUSES
    # `recover_interrupted_runs` barre running Y queued.
    import inspect

    from core import resilience

    fuente = inspect.getsource(resilience.recover_interrupted_runs)
    assert '"running", "queued"' in fuente


# ── Una operación destructiva tiene que destruir lo que promete ───────────────
# "Restablecer instalación" no borraba `agent-memory` ni `agent-soul`: el usuario
# creía arrancar limpio y arrastraba las memorias de la instalación anterior. Un
# reset a medias es peor que ninguno, porque nadie vuelve a revisarlo.

@pytest.mark.asyncio
async def test_reset_deletes_memories_and_lineage(tmp_path, monkeypatch):
    from core.api.admin import reset_install

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    mem = tmp_path / "agent-memory" / "un-agente"
    soul = tmp_path / "agent-soul" / "un-agente"
    mem.mkdir(parents=True)
    soul.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("- algo aprendido\n", encoding="utf-8")
    (mem / "20260101-x.md").write_text("cuerpo\n", encoding="utf-8")
    (soul / "lineage.json").write_text("{}\n", encoding="utf-8")

    result = await reset_install(confirm="YES_RESET_EVERYTHING")

    borrados = " ".join(result["deleted"])
    assert "MEMORY.md" in borrados, f"las memorias siguen ahí: {result['deleted']}"
    assert "lineage.json" in borrados, "el linaje de evolución sigue ahí"
    assert not (mem / "MEMORY.md").exists()
    assert not (soul / "lineage.json").exists()


@pytest.mark.asyncio
async def test_reset_still_refuses_without_the_confirmation(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from core.api.admin import reset_install

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    with pytest.raises(HTTPException) as ei:
        await reset_install(confirm="")
    assert ei.value.status_code == 400


def test_the_warning_names_what_gets_deleted():
    """Si el texto no nombra las memorias, el usuario no sabe qué está firmando."""
    from core.config import REPO_ROOT

    i18n = (REPO_ROOT / "dashboard/src/lib/i18n.tsx").read_text(encoding="utf-8")
    bloque = i18n[i18n.index('"settings.dangerZoneDescription"'):]
    bloque = bloque[:400].lower()
    assert "memoria" in bloque
    assert "irreversible" in bloque
