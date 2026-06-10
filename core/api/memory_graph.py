"""Global memory graph — feeds the dashboard's Obsidian-style network view."""
from __future__ import annotations

from fastapi import APIRouter

from core.memory.graph import build_memory_graph

router = APIRouter(prefix="/memory-graph", tags=["memories"])


@router.get("")
async def memory_graph() -> dict:
    """Nodes + edges of every agent's memory network (wikilinks included)."""
    return build_memory_graph()
