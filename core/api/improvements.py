"""Self-improving proposals — list, approve, reject, apply."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc, select

from core.db import async_session_factory
from core.db.models import Improvement

router = APIRouter(prefix="/improvements", tags=["improvements"])


@router.get("")
async def list_proposals(status: str = "proposed") -> list[dict]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Improvement).where(Improvement.status == status).order_by(desc(Improvement.id))
        )).scalars().all()
        return [
            {
                "id": i.id,
                "agent_id": i.agent_id,
                "rationale": i.rationale,
                "diff": i.proposed_diff_md,
                "created_at": i.created_at.isoformat(),
            }
            for i in rows
        ]


@router.post("/{improvement_id}/approve")
async def approve(improvement_id: int) -> dict:
    """Mark approved. Application is a separate explicit step (apply endpoint)."""
    async with async_session_factory() as session:
        imp = await session.get(Improvement, improvement_id)
        if imp is None:
            raise HTTPException(status_code=404, detail="improvement not found")
        imp.status = "approved"
        imp.reviewed_at = dt.datetime.now(dt.UTC)
        await session.commit()
    return {"status": "approved"}


@router.post("/{improvement_id}/reject")
async def reject(improvement_id: int, reason: str = "") -> dict:
    async with async_session_factory() as session:
        imp = await session.get(Improvement, improvement_id)
        if imp is None:
            raise HTTPException(status_code=404, detail="improvement not found")
        imp.status = "rejected"
        imp.reviewed_at = dt.datetime.now(dt.UTC)
        imp.rationale = (imp.rationale or "") + f"\n\nRejected: {reason}" if reason else imp.rationale
        await session.commit()
    return {"status": "rejected"}
