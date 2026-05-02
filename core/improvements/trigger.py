"""Decide whether an agent is due for a self-improvement reflection."""
from __future__ import annotations

from sqlalchemy import desc, select

from core.db import async_session_factory
from core.db.models import Improvement, Run


async def is_due(agent_id: int) -> bool:
    """Trigger reflection if last 3 runs failed OR every 10 runs without an open proposal."""
    async with async_session_factory() as session:
        last = (await session.execute(
            select(Run).where(Run.agent_id == agent_id).order_by(desc(Run.id)).limit(10)
        )).scalars().all()
        if not last:
            return False

        last_three = last[:3]
        if len(last_three) == 3 and all(r.status == "failed" for r in last_three):
            return True

        open_proposal = (await session.execute(
            select(Improvement).where(
                Improvement.agent_id == agent_id, Improvement.status == "proposed"
            ).limit(1)
        )).scalar_one_or_none()
        if open_proposal is not None:
            return False

        return len(last) >= 10
