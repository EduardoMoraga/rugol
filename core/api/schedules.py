"""Schedules CRUD."""
from __future__ import annotations

import logging

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from core.db import async_session_factory
from core.db.models import Agent, Schedule
from core.scheduler import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    agent_id: int
    cron_expr: str = Field(min_length=4, max_length=64)
    prompt: str = Field(min_length=1, max_length=4000)
    enabled: bool = True


def _validate_cron(expr: str) -> None:
    """Audit-fix: refuse malformed cron before it reaches APScheduler.

    APScheduler raises an opaque ValueError mid-job-add that previously
    crashed the request without clearing the half-inserted DB row.
    """
    try:
        # APScheduler's CronTrigger has the same parser the scheduler uses.
        CronTrigger.from_crontab(expr)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cron expression '{expr}' inválida: {e}. Usá 5 campos separados por espacios (e.g. '0 9 * * 1-5').",
        )


class ScheduleDTO(BaseModel):
    id: int
    agent_id: int
    cron_expr: str
    prompt: str
    enabled: bool
    next_run_at: str | None = None
    last_run_at: str | None = None


@router.get("", response_model=list[ScheduleDTO])
async def list_schedules() -> list[ScheduleDTO]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(Schedule))).scalars().all()
        return [
            ScheduleDTO(
                id=s.id, agent_id=s.agent_id, cron_expr=s.cron_expr,
                prompt=s.prompt, enabled=s.enabled,
                next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
                last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
            )
            for s in rows
        ]


@router.post("", status_code=201, response_model=ScheduleDTO)
async def create_schedule(body: ScheduleCreate) -> ScheduleDTO:
    _validate_cron(body.cron_expr)
    async with async_session_factory() as session:
        agent = await session.get(Agent, body.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        s = Schedule(
            agent_id=body.agent_id, cron_expr=body.cron_expr,
            prompt=body.prompt, enabled=body.enabled,
        )
        session.add(s)
        await session.flush()
        sched_id = s.id
        # Add to scheduler BEFORE commit so a scheduler failure rolls back the row.
        if body.enabled:
            try:
                get_scheduler().add_cron(sched_id, agent.name, body.prompt, body.cron_expr)
            except Exception as e:
                await session.rollback()
                logger.exception("scheduler.add_cron failed for cron=%s", body.cron_expr)
                raise HTTPException(status_code=400, detail=f"Scheduler rejected cron: {e}")
        await session.commit()
        return ScheduleDTO(
            id=s.id, agent_id=s.agent_id, cron_expr=s.cron_expr,
            prompt=s.prompt, enabled=s.enabled,
            next_run_at=None, last_run_at=None,
        )


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int) -> None:
    # Audit-fix: remove from scheduler FIRST. If the in-memory job dies
    # before the DB row, the next reload picks up an orphan job pointing
    # at a deleted Schedule. Reverse order eliminates that window.
    try:
        get_scheduler().remove(schedule_id)
    except Exception:
        # If the scheduler doesn't know about this id, that's fine — keep
        # going to clean up the DB row.
        logger.warning("scheduler.remove(%s) failed (job may already be gone)", schedule_id)
    async with async_session_factory() as session:
        s = await session.get(Schedule, schedule_id)
        if s is None:
            return
        await session.delete(s)
        await session.commit()
