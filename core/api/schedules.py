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
    # v0.6.x — drift detection between DB and APScheduler. When the row in
    # `schedules` says one cron but the live job in APScheduler is firing on
    # a different one (because somebody edited the DB without reloading,
    # or an old job survived a migration), this lets the UI show it.
    runtime_trigger: str | None = None
    runtime_drift: bool = False


@router.get("", response_model=list[ScheduleDTO])
async def list_schedules() -> list[ScheduleDTO]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(Schedule))).scalars().all()
    # Enrich each row with whatever APScheduler currently has loaded for it.
    live_jobs = {j["id"]: j for j in get_scheduler().list_jobs()}
    out: list[ScheduleDTO] = []
    for s in rows:
        live = live_jobs.get(f"schedule:{s.id}")
        runtime_next = live["next_run_time"] if live else None
        runtime_trig = live["trigger"] if live else None
        # Heuristic drift detection: see if the DB cron string appears
        # somewhere inside the trigger repr. APScheduler's repr is e.g.
        # "cron[minute='0', hour='12', day_of_week='1-5']". We compare the
        # 5 fields of the DB cron against the trigger repr — if any field
        # is missing, flag drift so the UI / tooling can surface it.
        drift = False
        if runtime_trig and s.cron_expr:
            db_fields = s.cron_expr.split()
            field_names = ["minute", "hour", "day", "month", "day_of_week"]
            for name, val in zip(field_names, db_fields, strict=False):
                if val == "*":
                    continue
                if f"{name}='{val}'" not in runtime_trig:
                    drift = True
                    break
        out.append(ScheduleDTO(
            id=s.id, agent_id=s.agent_id, cron_expr=s.cron_expr,
            prompt=s.prompt, enabled=s.enabled,
            next_run_at=runtime_next or (s.next_run_at.isoformat() if s.next_run_at else None),
            last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
            runtime_trigger=runtime_trig,
            runtime_drift=drift,
        ))
    return out


@router.get("/runtime")
async def list_runtime_jobs() -> dict:
    """Return APScheduler's current view of jobs — the source of truth for what fires.

    Useful for debugging when /schedules (the DB view) and the actual
    behaviour disagree. Each entry shows the parsed cron trigger and the
    next_run_time APScheduler computed.
    """
    return {"jobs": get_scheduler().list_jobs()}


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


class ScheduleUpdate(BaseModel):
    """All fields optional; only the ones provided get changed."""
    cron_expr: str | None = Field(default=None, min_length=4, max_length=64)
    prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    enabled: bool | None = None


@router.put("/{schedule_id}", response_model=ScheduleDTO)
async def update_schedule(schedule_id: int, body: ScheduleUpdate) -> ScheduleDTO:
    """Edit an existing schedule. Atomically syncs DB row + APScheduler trigger.

    Use this instead of DELETE + POST to change a cron expression — the
    delete+create cycle has caused drift in the past (the new POST gets
    accepted by APScheduler with replace_existing=True, but if anything
    interleaves, the old trigger can survive).
    """
    if body.cron_expr is not None:
        _validate_cron(body.cron_expr)

    sched = get_scheduler()
    async with async_session_factory() as session:
        s = await session.get(Schedule, schedule_id)
        if s is None:
            raise HTTPException(status_code=404, detail="schedule not found")
        agent = await session.get(Agent, s.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="agent for schedule not found")

        # Apply DB changes first (in-session, not yet committed).
        if body.cron_expr is not None:
            s.cron_expr = body.cron_expr
        if body.prompt is not None:
            s.prompt = body.prompt
        if body.enabled is not None:
            s.enabled = body.enabled

        # Sync APScheduler. Two cases:
        # 1) The schedule is now enabled → register/replace trigger with the
        #    new cron + prompt.
        # 2) Disabled → remove the live job.
        try:
            if s.enabled:
                sched.add_cron(s.id, agent.name, s.prompt, s.cron_expr)
            else:
                sched.remove(s.id)
        except Exception as e:
            await session.rollback()
            logger.exception("scheduler sync failed for update of %s", schedule_id)
            raise HTTPException(status_code=400, detail=f"Scheduler rejected update: {e}")

        await session.commit()

        # Return enriched DTO with runtime info, same shape as GET.
        live = sched.job_for_schedule(s.id)
        runtime_next = live["next_run_time"] if live else None
        runtime_trig = live["trigger"] if live else None
        return ScheduleDTO(
            id=s.id, agent_id=s.agent_id, cron_expr=s.cron_expr,
            prompt=s.prompt, enabled=s.enabled,
            next_run_at=runtime_next or (s.next_run_at.isoformat() if s.next_run_at else None),
            last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
            runtime_trigger=runtime_trig,
            runtime_drift=False,
        )


@router.post("/resync")
async def resync_schedules() -> dict:
    """Force APScheduler's job set to match the DB rows.

    For every enabled schedule, re-register it in APScheduler with
    replace_existing=True so the trigger stored in the jobstore matches
    the cron expression in the DB. Then drop any APScheduler job that
    points at a schedule_id no longer in the DB.

    Use case: drift between DB cron and APScheduler trigger (detected by
    GET /schedules's runtime_drift flag).
    """
    sched = get_scheduler()
    db_schedule_ids: set[int] = set()
    fixed: list[int] = []
    removed_orphans: list[str] = []
    async with async_session_factory() as session:
        rows = (await session.execute(select(Schedule))).scalars().all()
        agent_ids = [r.agent_id for r in rows]
        agents = (
            await session.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        ).scalars().all() if agent_ids else []
        agents_by_id = {a.id: a for a in agents}
        for s in rows:
            db_schedule_ids.add(s.id)
            if not s.enabled:
                # Disabled rows shouldn't have a live job — remove if present.
                sched.remove(s.id)
                continue
            agent = agents_by_id.get(s.agent_id)
            if agent is None:
                continue
            try:
                sched.add_cron(s.id, agent.name, s.prompt, s.cron_expr)
                fixed.append(s.id)
            except Exception:
                logger.exception("resync: failed to add schedule %s", s.id)
    # Remove orphan jobs in APScheduler whose schedule_id is no longer in DB.
    for job in sched.list_jobs():
        jid = job["id"]
        if not jid.startswith("schedule:"):
            continue
        try:
            sid = int(jid.split(":", 1)[1])
        except ValueError:
            continue
        if sid not in db_schedule_ids:
            sched.remove(sid)
            removed_orphans.append(jid)
    return {
        "ok": True,
        "fixed_count": len(fixed),
        "fixed_ids": fixed,
        "removed_orphans": removed_orphans,
    }


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
