"""Schedules CRUD."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from core.db import async_session_factory
from core.db.models import Agent, Schedule
from core.scheduler import get_scheduler

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    agent_id: int
    cron_expr: str
    prompt: str
    enabled: bool = True


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
        if body.enabled:
            get_scheduler().add_cron(sched_id, agent.name, body.prompt, body.cron_expr)
        await session.commit()
        return ScheduleDTO(
            id=s.id, agent_id=s.agent_id, cron_expr=s.cron_expr,
            prompt=s.prompt, enabled=s.enabled,
            next_run_at=None, last_run_at=None,
        )


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int) -> None:
    async with async_session_factory() as session:
        s = await session.get(Schedule, schedule_id)
        if s is None:
            return
        await session.delete(s)
        await session.commit()
    get_scheduler().remove(schedule_id)
