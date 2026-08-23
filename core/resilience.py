"""Volver a operar solo, después de un corte.

El escenario que este módulo cubre: se corta la luz en medio de una corrida.
Sin esto, cuando la máquina vuelve pasan cuatro cosas, todas silenciosas:

  1. La corrida que estaba a mitad queda `status="running"` para siempre. El
     dashboard muestra un agente trabajando que no existe, y la vista de flota
     miente.
  2. El agente queda `status="running"` y nunca vuelve a `idle`.
  3. SQLite en journal mode `delete` (el default) puede quedar con un journal
     a medias.
  4. Nadie se enteró de nada.

Todo lo de acá corre una vez, al arrancar el core, ANTES de que el scheduler
empiece a disparar y antes de que los adaptadores acepten mensajes.
"""
from __future__ import annotations

import datetime as dt
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import event, select, text, update

logger = logging.getLogger(__name__)

# Estado terminal para lo que quedó a mitad de camino. No usamos "failed"
# a secas: el agente no falló, lo interrumpieron, y esa diferencia importa
# cuando el bucle self-improving cuenta fracasos para proponer cambios.
INTERRUPTED_MESSAGE = (
    "Interrumpido por un reinicio o corte de la máquina "
    "(la corrida estaba activa cuando el core se apagó)."
)


@dataclass
class RecoveryReport:
    """Qué encontró el arranque. Se loguea y se expone en /api/health/full."""

    interrupted_runs: int = 0
    reset_agents: int = 0
    integrity: str = "no verificado"
    backup: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return (
            self.interrupted_runs == 0
            and self.reset_agents == 0
            and self.integrity in ("ok", "no verificado")
        )

    def as_dict(self) -> dict:
        return {
            "interrupted_runs": self.interrupted_runs,
            "reset_agents": self.reset_agents,
            "integrity": self.integrity,
            "backup": self.backup,
            "notes": list(self.notes),
            "clean": self.clean,
        }


# ── 1. SQLite que sobrevive a un corte ───────────────────────────────────────
def harden_sqlite(sync_engine) -> None:
    """WAL + `synchronous=NORMAL` + espera en vez de 'database is locked'.

    - `journal_mode=WAL`: los lectores no se bloquean con el escritor, y un
      corte deja un WAL que SQLite reproduce solo al abrir. Es la diferencia
      entre "vuelve" y "vuelve corrupto".
    - `synchronous=NORMAL`: con WAL, es durable ante caída del proceso y
      cuesta órdenes de magnitud menos que FULL. Un corte de luz puede perder
      la última transacción; para runs y schedules eso es aceptable.
    - `busy_timeout`: el scheduler y el API escriben a la vez. Sin esto,
      SQLite devuelve "database is locked" al instante en vez de esperar.
    - `foreign_keys=ON`: SQLite los ignora por default, y el esquema los usa
      con ON DELETE CASCADE.

    Se aplica por conexión, que es la única forma de que valga para todas las
    del pool.
    """

    @event.listens_for(sync_engine, "connect")
    def _set_pragmas(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA foreign_keys=ON")
        except Exception:
            # Postgres u otro backend, o un SQLite que no acepta el pragma:
            # no es fatal, sólo perdemos el endurecimiento.
            logger.debug("no pude aplicar los pragmas de SQLite", exc_info=True)
        finally:
            cursor.close()


# ── 2. Copia rotativa antes de tocar nada ────────────────────────────────────
def backup_database(*, keep: int = 3) -> str:
    """Copia la DB al arrancar y conserva las últimas `keep`.

    Barato (un archivo de pocos MB) y es la única red que hay si una migración
    sale mal o el archivo se daña. Devuelve el nombre del backup, o "" si no
    aplica (Postgres, o la DB todavía no existe).
    """
    from core.config import data_dir, get_settings

    url = get_settings().DATABASE_URL
    if not url.startswith("sqlite"):
        return ""
    db_path = Path(url.split(":///")[-1])
    if not db_path.is_file() or db_path.stat().st_size == 0:
        return ""

    backups = data_dir() / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backups / f"{db_path.stem}-{stamp}.db"
    try:
        shutil.copy2(db_path, dest)
    except OSError as e:
        logger.warning("no pude respaldar la base: %s", e)
        return ""

    # Rotación: nos quedamos con las `keep` más nuevas.
    existing = sorted(
        backups.glob(f"{db_path.stem}-*.db"), key=lambda p: p.name, reverse=True
    )
    for stale in existing[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass
    return dest.name


# ── 3. Chequeo de integridad ─────────────────────────────────────────────────
async def integrity_check() -> str:
    """`PRAGMA quick_check` — barato y detecta el daño que importa."""
    from core.config import get_settings
    from core.db import engine

    if not get_settings().DATABASE_URL.startswith("sqlite"):
        return "no aplica (no es SQLite)"
    try:
        async with engine.connect() as conn:
            result = (await conn.execute(text("PRAGMA quick_check"))).scalar()
        return "ok" if str(result).lower() == "ok" else str(result)
    except Exception as e:
        return f"no verificado ({e})"


# ── 4. Lo que quedó a mitad de camino ────────────────────────────────────────
async def recover_interrupted_runs() -> tuple[int, int]:
    """Cierra las corridas colgadas y devuelve los agentes a `idle`.

    Se llama en el arranque, cuando por definición no hay ninguna corrida viva
    en este proceso: cualquier fila en `running`/`queued` es basura de la
    encarnación anterior.

    Devuelve (corridas cerradas, agentes reseteados).
    """
    from core.db import async_session_factory
    from core.db.models import Agent, Run

    now = dt.datetime.now(dt.UTC)
    async with async_session_factory() as session:
        stuck = (await session.execute(
            select(Run.id).where(Run.status.in_(("running", "queued")))
        )).scalars().all()

        if stuck:
            await session.execute(
                update(Run)
                .where(Run.id.in_(stuck))
                .values(status="interrupted", ended_at=now, error_message=INTERRUPTED_MESSAGE)
            )

        # Los agentes que quedaron marcados como ocupados o en error por una
        # corrida que ya no existe vuelven a idle. Sin esto la vista de flota
        # muestra actividad fantasma hasta la próxima corrida de cada agente.
        agents_result = await session.execute(
            update(Agent)
            .where(Agent.status.in_(("running", "error")))
            .values(status="idle")
        )
        await session.commit()

    return len(stuck), int(agents_result.rowcount or 0)


# ── 5. Orquestación ──────────────────────────────────────────────────────────
async def startup_recovery(*, backup: bool = True) -> RecoveryReport:
    """Todo el arranque defensivo, en orden, sin poder tumbar el boot.

    Ninguna de estas etapas es motivo para no arrancar: un Rugol que levanta
    con una advertencia sirve, uno que no levanta no.
    """
    report = RecoveryReport()

    if backup:
        try:
            report.backup = backup_database()
        except Exception:
            logger.exception("el respaldo de arranque falló — sigo")
            report.notes.append("el respaldo falló")

    try:
        report.integrity = await integrity_check()
        if report.integrity not in ("ok", "no verificado") and not report.integrity.startswith(
            "no aplica"
        ):
            logger.error("integridad de la base: %s", report.integrity)
            report.notes.append(f"integridad: {report.integrity}")
    except Exception:
        logger.exception("el chequeo de integridad falló — sigo")

    try:
        runs, agents = await recover_interrupted_runs()
        report.interrupted_runs, report.reset_agents = runs, agents
        if runs or agents:
            logger.warning(
                "recuperación de arranque: %d corrida(s) interrumpida(s) cerradas, "
                "%d agente(s) devuelto(s) a idle",
                runs, agents,
            )
    except Exception:
        logger.exception("no pude recuperar las corridas interrumpidas — sigo")
        report.notes.append("la recuperación de corridas falló")

    if report.clean and not report.notes:
        logger.info("recuperación de arranque: nada pendiente (integridad %s)", report.integrity)
    return report


_last_report: RecoveryReport | None = None


def set_last_report(report: RecoveryReport) -> None:
    global _last_report
    _last_report = report


def last_report() -> RecoveryReport | None:
    """Lo que encontró el último arranque, para /api/health/full."""
    return _last_report
