"""Runs queries (cross-agent)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc, select

from core.db import async_session_factory
from core.db.models import Run
from core.runner.orchestrator import get_orchestrator

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
async def list_recent(limit: int = 100) -> list[dict]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Run).order_by(desc(Run.id)).limit(limit)
        )).scalars().all()
        return [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "source": r.source,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "cost_usd": r.cost_usd,
            }
            for r in rows
        ]


@router.get("/{run_id}")
async def get_run(run_id: int) -> dict:
    async with async_session_factory() as session:
        r = await session.get(Run, run_id)
        if r is None:
            raise HTTPException(status_code=404, detail="run not found")
        return {
            "id": r.id,
            "agent_id": r.agent_id,
            "source": r.source,
            "status": r.status,
            "prompt": r.prompt,
            "started_at": r.started_at.isoformat(),
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": r.cost_usd,
            "session_id": r.session_id,
            "error_message": r.error_message,
        }


@router.post("/{run_id}/cancel", status_code=202)
async def cancel(run_id: int) -> dict:
    ok = get_orchestrator().cancel(run_id)
    return {"cancelled": ok}
