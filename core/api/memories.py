"""Per-agent memory CRUD over HTTP — backs the dashboard's Memoria tab."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.db import async_session_factory
from core.db.models import Agent
from core.memory import add_memory, delete_memory, list_memories

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["memories"])


class MemoryDTO(BaseModel):
    name: str
    description: str
    kind: str
    created_at: str
    body: str
    file: str


class NewMemory(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    body: str = Field(min_length=1)
    kind: str = Field(default="note", max_length=32)


async def _agent_name(agent_id: int) -> str:
    async with async_session_factory() as session:
        a = await session.get(Agent, agent_id)
        if a is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return a.name


@router.get("/{agent_id}/memories", response_model=list[MemoryDTO])
async def list_agent_memories(agent_id: int) -> list[MemoryDTO]:
    name = await _agent_name(agent_id)
    return [MemoryDTO(**m.as_dict()) for m in list_memories(name)]


@router.post("/{agent_id}/memories", status_code=201, response_model=MemoryDTO)
async def create_agent_memory(agent_id: int, body: NewMemory) -> MemoryDTO:
    name = await _agent_name(agent_id)
    mem = add_memory(
        agent_name=name,
        name=body.name,
        description=body.description,
        content=body.body,
        kind=body.kind,
    )
    return MemoryDTO(**mem.as_dict())


@router.delete("/{agent_id}/memories/{file_or_name}")
async def delete_agent_memory(agent_id: int, file_or_name: str) -> dict:
    name = await _agent_name(agent_id)
    ok = delete_memory(name, file_or_name)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"ok": True}
