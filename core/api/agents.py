"""Agents CRUD + run-now."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select

from core.db import async_session_factory
from core.db.models import Agent, Run
from core.runner.orchestrator import RunRequest, get_orchestrator

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentDTO(BaseModel):
    id: int
    name: str
    model: str
    description: str
    status: str
    last_run_at: str | None = None


class RunNowBody(BaseModel):
    prompt: str
    session_id: str | None = None


@router.get("", response_model=list[AgentDTO])
async def list_agents() -> list[AgentDTO]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(Agent).order_by(Agent.name))).scalars().all()
        return [
            AgentDTO(
                id=a.id,
                name=a.name,
                model=a.model,
                description=a.description,
                status=a.status,
                last_run_at=a.last_run_at.isoformat() if a.last_run_at else None,
            )
            for a in rows
        ]


@router.get("/{agent_id}", response_model=AgentDTO)
async def get_agent(agent_id: int) -> AgentDTO:
    async with async_session_factory() as session:
        a = await session.get(Agent, agent_id)
        if a is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return AgentDTO(
            id=a.id, name=a.name, model=a.model, description=a.description,
            status=a.status,
            last_run_at=a.last_run_at.isoformat() if a.last_run_at else None,
        )


@router.post("/{agent_id}/run", status_code=202)
async def run_now(agent_id: int, body: RunNowBody) -> dict:
    async with async_session_factory() as session:
        a = await session.get(Agent, agent_id)
        if a is None:
            raise HTTPException(status_code=404, detail="agent not found")
        agent_name = a.name

    run_id = await get_orchestrator().enqueue(RunRequest(
        agent_name=agent_name,
        prompt=body.prompt,
        source="dashboard",
        session_id=body.session_id,
    ))
    return {"run_id": run_id, "status": "queued"}


@router.get("/{agent_id}/runs")
async def list_runs(agent_id: int, limit: int = 50) -> list[dict]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Run).where(Run.agent_id == agent_id).order_by(desc(Run.id)).limit(limit)
        )).scalars().all()
        return [
            {
                "id": r.id,
                "source": r.source,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
                "prompt": r.prompt[:200],
                "error_message": r.error_message,
            }
            for r in rows
        ]
