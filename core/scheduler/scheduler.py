"""APScheduler wrapper. Persists jobs to SQLite (separate DB to avoid lock contention)."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import get_settings
from core.runner.orchestrator import RunRequest, get_orchestrator

logger = logging.getLogger(__name__)


class RogologoScheduler:
    def __init__(self, jobstore_path: Path) -> None:
        jobstore_path.parent.mkdir(parents=True, exist_ok=True)
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{jobstore_path}")},
            executors={"default": AsyncIOExecutor()},
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
            timezone="UTC",
        )

    def start(self) -> None:
        self._scheduler.start()
        logger.info("scheduler started")

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def add_cron(self, schedule_id: int, agent_name: str, prompt: str, cron_expr: str) -> None:
        """Add or replace a cron-triggered job."""
        trigger = CronTrigger.from_crontab(cron_expr, timezone="UTC")
        self._scheduler.add_job(
            _fire_schedule,
            trigger=trigger,
            args=[schedule_id, agent_name, prompt],
            id=f"schedule:{schedule_id}",
            replace_existing=True,
        )
        logger.info("scheduled %s → %s on %s", schedule_id, agent_name, cron_expr)

    def remove(self, schedule_id: int) -> None:
        try:
            self._scheduler.remove_job(f"schedule:{schedule_id}")
        except Exception:
            pass

    def list_jobs(self) -> list[dict]:
        return [
            {
                "id": j.id,
                "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
            }
            for j in self._scheduler.get_jobs()
        ]


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


_scheduler_instance: RogologoScheduler | None = None


def get_scheduler() -> RogologoScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        settings = get_settings()
        repo_root = Path(__file__).resolve().parent.parent.parent
        _scheduler_instance = RogologoScheduler(jobstore_path=repo_root / "data" / "scheduler.db")
    return _scheduler_instance
