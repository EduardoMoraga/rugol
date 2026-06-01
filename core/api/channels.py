"""Channel bindings — map an external chat/channel to a Rugol agent.

A binding is the contract between a Telegram chat (or Slack channel) and the
agent that should handle messages from there. Without a binding, the adapter
sends a help message instead of dispatching to a wrong default.

Endpoints:
    GET    /api/channels                         list all bindings
    POST   /api/channels                         create a binding
    DELETE /api/channels/{id}                    remove a binding
    GET    /api/channels/lookup/{type}/{ext_id}  internal lookup helper
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, ChannelBinding

router = APIRouter(prefix="/channels", tags=["channels"])

VALID_TYPES = {"telegram", "slack"}


class ChannelBindingDTO(BaseModel):
    id: int
    channel_type: str
    external_id: str
    agent_id: int
    agent_name: str
    project_slug: str | None = None
    project_name: str | None = None
    label: str | None = None
    created_at: str


class ChannelBindingCreate(BaseModel):
    channel_type: str = Field(min_length=2, max_length=16)
    external_id: str = Field(min_length=1, max_length=128)
    agent_id: int
    label: str | None = None


def _to_dto(b: ChannelBinding, agent: Agent) -> ChannelBindingDTO:
    proj = agent.project if hasattr(agent, "project") else None
    return ChannelBindingDTO(
        id=b.id,
        channel_type=b.channel_type,
        external_id=b.external_id,
        agent_id=b.agent_id,
        agent_name=agent.name,
        project_slug=proj.slug if proj else None,
        project_name=proj.name if proj else None,
        label=b.label,
        created_at=b.created_at.isoformat() if b.created_at else "",
    )


@router.get("", response_model=list[ChannelBindingDTO])
async def list_bindings(channel_type: str | None = None) -> list[ChannelBindingDTO]:
    async with async_session_factory() as session:
        stmt = select(ChannelBinding).order_by(ChannelBinding.created_at.desc())
        if channel_type:
            stmt = stmt.where(ChannelBinding.channel_type == channel_type.lower())
        bindings = (await session.execute(stmt)).scalars().all()
        agent_ids = [b.agent_id for b in bindings]
        if not agent_ids:
            return []
        agents = (await session.execute(
            select(Agent).where(Agent.id.in_(agent_ids)).options(selectinload(Agent.project))
        )).scalars().all()
        agents_by_id = {a.id: a for a in agents}
        out: list[ChannelBindingDTO] = []
        for b in bindings:
            a = agents_by_id.get(b.agent_id)
            if a:
                out.append(_to_dto(b, a))
        return out


@router.post("", response_model=ChannelBindingDTO, status_code=201)
async def create_binding(body: ChannelBindingCreate) -> ChannelBindingDTO:
    if body.channel_type.lower() not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"channel_type must be one of {VALID_TYPES}")
    async with async_session_factory() as session:
        agent = (await session.execute(
            select(Agent).where(Agent.id == body.agent_id).options(selectinload(Agent.project))
        )).scalar_one_or_none()
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        # Replace existing binding for this channel — one agent per channel.
        existing = (await session.execute(
            select(ChannelBinding).where(
                ChannelBinding.channel_type == body.channel_type.lower(),
                ChannelBinding.external_id == body.external_id,
            )
        )).scalar_one_or_none()
        if existing is not None:
            existing.agent_id = body.agent_id
            existing.label = body.label
            await session.commit()
            await session.refresh(existing)
            await bus.publish("channel:rebound", {
                "channel_type": existing.channel_type,
                "external_id": existing.external_id,
                "agent": agent.name,
            })
            return _to_dto(existing, agent)
        b = ChannelBinding(
            channel_type=body.channel_type.lower(),
            external_id=body.external_id,
            agent_id=body.agent_id,
            label=body.label,
        )
        session.add(b)
        await session.commit()
        await session.refresh(b)
        await bus.publish("channel:bound", {
            "channel_type": b.channel_type,
            "external_id": b.external_id,
            "agent": agent.name,
        })
        return _to_dto(b, agent)


@router.delete("/{binding_id}", status_code=204)
async def delete_binding(binding_id: int) -> None:
    async with async_session_factory() as session:
        b = await session.get(ChannelBinding, binding_id)
        if b is None:
            raise HTTPException(status_code=404, detail="binding not found")
        ext = b.external_id
        ctype = b.channel_type
        await session.delete(b)
        await session.commit()
        await bus.publish("channel:unbound", {"channel_type": ctype, "external_id": ext})


@router.get("/lookup/{channel_type}/{external_id}")
async def lookup(channel_type: str, external_id: str) -> dict:
    """Internal helper for adapters: find which agent handles this channel."""
    async with async_session_factory() as session:
        b = (await session.execute(
            select(ChannelBinding).where(
                ChannelBinding.channel_type == channel_type.lower(),
                ChannelBinding.external_id == external_id,
            )
        )).scalar_one_or_none()
        if b is None:
            raise HTTPException(status_code=404, detail="binding not found")
        agent = await session.get(Agent, b.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="bound agent missing")
        return {
            "binding_id": b.id,
            "agent_id": agent.id,
            "agent_name": agent.name,
            "label": b.label,
        }
