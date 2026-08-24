"""APScheduler wrapper. Persists jobs to SQLite (separate DB to avoid lock contention)."""
from __future__ import annotations

import logging
from pathlib import Path

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import get_settings
from core.runner.orchestrator import RunRequest, get_orchestrator

logger = logging.getLogger(__name__)


class RugolScheduler:
    def __init__(self, jobstore_path: Path) -> None:
        jobstore_path.parent.mkdir(parents=True, exist_ok=True)
        tz = get_settings().SCHEDULER_TIMEZONE or "UTC"
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{jobstore_path}")},
            executors={"default": AsyncIOExecutor()},
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
            timezone=tz,
        )
        self._timezone = tz

    def start(self) -> None:
        self._scheduler.start()
        logger.info("scheduler started (timezone=%s)", self._timezone)

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def add_cron(self, schedule_id: int, agent_name: str, prompt: str, cron_expr: str) -> None:
        """Add or replace a cron-triggered job.

        Cron expressions are interpreted in the SCHEDULER_TIMEZONE setting
        (default America/Santiago). A user writing "0 8 * * 1-5" expects
        8 AM their time, not 8 AM UTC.
        """
        trigger = CronTrigger.from_crontab(cron_expr, timezone=self._timezone)
        self._scheduler.add_job(
            _fire_schedule,
            trigger=trigger,
            args=[schedule_id, agent_name, prompt],
            id=f"schedule:{schedule_id}",
            replace_existing=True,
        )
        logger.info(
            "scheduled %s → %s on %s (%s)",
            schedule_id, agent_name, cron_expr, self._timezone,
        )

    def remove(self, schedule_id: int) -> None:
        try:
            self._scheduler.remove_job(f"schedule:{schedule_id}")
        except Exception:
            pass

    def add_voice_sync_job(self, interval_minutes: int = 5) -> None:
        """Job interno que sincroniza entrevistas de voz cada N minutos.

        No es un Schedule de usuario (no toca la tabla schedules ni el
        orchestrator): es un job de mantenimiento de la integración de voz.
        Idempotente — sync_interviews no reprocesa conversaciones ya en el
        pipeline. Se registra solo si hay ELEVENLABS_API_KEY (lo decide main).
        """
        from apscheduler.triggers.interval import IntervalTrigger

        self._scheduler.add_job(
            _fire_voice_sync,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="voice:sync",
            replace_existing=True,
            next_run_time=None,  # arranca en el primer intervalo, no al boot
        )
        logger.info("voice sync job programado cada %s min", interval_minutes)

    def add_maintenance_job(self, hours: int = 1) -> None:
        """Mantenimiento horario: respaldo diario de la base y barrido de logs.

        Existe porque Rugol vive en una máquina que no se reinicia. Todo lo que
        colgaba del arranque —el respaldo, la rotación— no pasaba nunca: se
        encontró una instalación con dos meses de uptime, un respaldo de dos
        meses (o sea ninguno) y un core.log de 143 MB.
        """
        from apscheduler.triggers.interval import IntervalTrigger

        self._scheduler.add_job(
            _fire_maintenance,
            trigger=IntervalTrigger(hours=hours),
            id="internal:maintenance",
            replace_existing=True,
            next_run_time=None,  # el arranque ya respaldó; empezamos en la 1ª hora
        )
        logger.info("mantenimiento programado cada %s h", hours)

    def list_jobs(self) -> list[dict]:
        """Return live state of every job APScheduler currently has loaded.

        Used by /api/schedules to enrich the DB rows with the trigger
        actually firing (which can drift from the DB row if migrations or
        manual DB edits skip the scheduler) and the next_run_time computed
        by APScheduler. Without this, GET /schedules always returned
        next_run_at=null because the DB column never gets populated.
        """
        out = []
        for j in self._scheduler.get_jobs():
            trigger_str = ""
            try:
                # CronTrigger.__str__ returns something like
                # "cron[minute='0', hour='9', ...]" — useful for debugging
                # drift between DB and scheduler.
                trigger_str = str(j.trigger)
            except Exception:
                trigger_str = "?"
            out.append({
                "id": j.id,
                "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                "trigger": trigger_str,
            })
        return out

    def job_for_schedule(self, schedule_id: int) -> dict | None:
        """Convenience: lookup a single job by schedule id."""
        target = f"schedule:{schedule_id}"
        for j in self._scheduler.get_jobs():
            if j.id == target:
                return {
                    "id": j.id,
                    "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                    "trigger": str(j.trigger),
                }
        return None


async def _fire_schedule(schedule_id: int, agent_name: str, prompt: str) -> None:
    """Job target — enqueues a run via the orchestrator."""
    orchestrator = get_orchestrator()
    try:
        await orchestrator.enqueue(RunRequest(
            agent_name=agent_name,
            prompt=prompt,
            source="schedule",
            schedule_id=schedule_id,
        ))
    except Exception:
        logger.exception("schedule %s failed to enqueue", schedule_id)
        return

    # `Schedule.last_run_at` no se escribía en NINGÚN lado: la pantalla de
    # Horarios decía "nunca corrió" incluso para uno que llevaba meses
    # disparando. Para un asistente que trabaja mientras nadie mira, no poder
    # ver si el briefing de la mañana se ejecutó es ceguera pura.
    try:
        import datetime as _dt

        from core.db import async_session_factory
        from core.db.models import Schedule

        async with async_session_factory() as session:
            row = await session.get(Schedule, schedule_id)
            if row is not None:
                row.last_run_at = _dt.datetime.now(_dt.UTC)
                await session.commit()
    except Exception:
        # Anotar el disparo es contabilidad: no puede hacer fallar la corrida.
        logger.exception("no pude registrar last_run_at del schedule %s", schedule_id)


async def _fire_maintenance() -> None:
    """Job interno. Nunca propaga: un fallo de mantenimiento no puede matar el scheduler."""
    import asyncio

    from core.maintenance import run_maintenance

    try:
        await asyncio.to_thread(run_maintenance)
    except Exception:
        logger.warning("mantenimiento: el ciclo falló", exc_info=True)


async def _fire_voice_sync() -> None:
    """Job target — sincroniza entrevistas de voz de ElevenLabs al pipeline."""
    from core.voice import sync_interviews

    try:
        result = await sync_interviews()
        if result.get("created") or result.get("errors"):
            logger.info("voice sync: %s", result)
    except Exception:
        logger.exception("voice sync job falló")


_scheduler_instance: RugolScheduler | None = None


def get_scheduler() -> RugolScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        # data_dir() (no la raíz del repo): el jobstore vive con el resto del
        # estado, fuera del directorio de la app — reinstalar borraba los
        # schedules cuando esto apuntaba al código.
        from core.config import adopt_legacy_data, data_dir
        adopt_legacy_data(("scheduler.db",))
        _scheduler_instance = RugolScheduler(jobstore_path=data_dir() / "scheduler.db")
    return _scheduler_instance
