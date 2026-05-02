"""Triple-store CRUD over OntologyNode/OntologyEdge.

Agents write via the MemoryWrite tool (typed); humans curate via the dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import async_session_factory
from core.db.models import OntologyEdge, OntologyNode


@dataclass
class Triple:
    src: str
    predicate: str
    dst: str


class OntologyStore:
    """High-level API on top of the relational triple store."""

    async def upsert_node(self, label: str, node_type: str = "entity", meta: dict | None = None) -> int:
        async with async_session_factory() as session:
            node = (await session.execute(
                select(OntologyNode).where(OntologyNode.label == label)
            )).scalar_one_or_none()
            if node is None:
                node = OntologyNode(label=label, type=node_type, meta=meta or {})
                session.add(node)
                await session.flush()
            else:
                if node_type and node.type != node_type:
                    node.type = node_type
                if meta:
                    merged = {**(node.meta or {}), **meta}
                    node.meta = merged
            await session.commit()
            return node.id

    async def add_edge(self, src_label: str, predicate: str, dst_label: str, run_id: int | None = None) -> int:
        src_id = await self.upsert_node(src_label)
        dst_id = await self.upsert_node(dst_label)
        async with async_session_factory() as session:
            edge = OntologyEdge(src=src_id, predicate=predicate, dst=dst_id, created_by_run=run_id)
            session.add(edge)
            await session.commit()
            return edge.id

    async def neighbors(self, label: str, predicate: str | None = None) -> list[Triple]:
        async with async_session_factory() as session:
            node = (await session.execute(
                select(OntologyNode).where(OntologyNode.label == label)
            )).scalar_one_or_none()
            if node is None:
                return []
            stmt = select(OntologyEdge, OntologyNode).join(
                OntologyNode, OntologyEdge.dst == OntologyNode.id
            ).where(OntologyEdge.src == node.id)
            if predicate:
                stmt = stmt.where(OntologyEdge.predicate == predicate)
            rows = (await session.execute(stmt)).all()
            return [Triple(src=label, predicate=e.predicate, dst=n.label) for e, n in rows]


_store: OntologyStore | None = None


def get_ontology() -> OntologyStore:
    global _store
    if _store is None:
        _store = OntologyStore()
    return _store
