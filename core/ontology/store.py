"""Triple-store CRUD over OntologyNode/OntologyEdge.

El grafo es la memoria COMPARTIDA: lo que un agente aprende sobre el mundo
queda disponible para los demás. Las memorias son privadas de cada agente; el
grafo es el terreno común.

Los agentes escriben con `remember_fact` / `recall_facts`, expuestas por MCP
sobre HTTP (core/mcp/memory_service.py), así que los dos motores —Claude y
Codex— usan el mismo grafo. Los humanos curan desde el dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased

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

    async def add_edge(
        self,
        src_label: str,
        predicate: str,
        dst_label: str,
        run_id: int | None = None,
    ) -> int:
        """Agrega la arista, o devuelve la que ya estaba.

        Idempotente a propósito: un agente que reafirma un hecho en cada corrida
        no puede multiplicar la misma arista. Sin esto, el grafo de un agente
        activo se vuelve ilegible en una semana —cien copias del mismo hecho— y
        la vista deja de servir para lo único que sirve, ver la forma del
        conocimiento.
        """
        src_id = await self.upsert_node(src_label)
        dst_id = await self.upsert_node(dst_label)
        async with async_session_factory() as session:
            existente = (await session.execute(
                select(OntologyEdge).where(
                    OntologyEdge.src == src_id,
                    OntologyEdge.predicate == predicate,
                    OntologyEdge.dst == dst_id,
                )
            )).scalars().first()
            if existente is not None:
                return existente.id
            edge = OntologyEdge(src=src_id, predicate=predicate, dst=dst_id, created_by_run=run_id)
            session.add(edge)
            await session.commit()
            return edge.id

    async def neighbors(self, label: str, predicate: str | None = None) -> list[Triple]:
        """Aristas que SALEN del nodo."""
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


    async def around(self, label: str, limit: int = 40) -> list[Triple]:
        """Todo lo que toca al nodo, en las dos direcciones.

        Para recordar, la dirección no importa: si un agente pregunta por
        "Philips" le sirve tanto "Philips → cliente_de → Increxa" como
        "reporte_semanal → pertenece_a → Philips". Mirar sólo las salientes deja
        la mitad del conocimiento invisible.
        """
        async with async_session_factory() as session:
            node = (await session.execute(
                select(OntologyNode).where(OntologyNode.label == label)
            )).scalar_one_or_none()
            if node is None:
                return []

            src_node = aliased(OntologyNode)
            dst_node = aliased(OntologyNode)
            stmt = (
                select(OntologyEdge, src_node.label, dst_node.label)
                .join(src_node, OntologyEdge.src == src_node.id)
                .join(dst_node, OntologyEdge.dst == dst_node.id)
                .where(or_(OntologyEdge.src == node.id, OntologyEdge.dst == node.id))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            return [
                Triple(src=src_label, predicate=e.predicate, dst=dst_label)
                for e, src_label, dst_label in rows
            ]

    async def search(self, query: str, limit: int = 40) -> list[Triple]:
        """Aristas donde el texto aparece en cualquiera de las tres posiciones."""
        needle = f"%{query.lower()}%"
        src_node = aliased(OntologyNode)
        dst_node = aliased(OntologyNode)
        async with async_session_factory() as session:
            stmt = (
                select(OntologyEdge, src_node.label, dst_node.label)
                .join(src_node, OntologyEdge.src == src_node.id)
                .join(dst_node, OntologyEdge.dst == dst_node.id)
                .where(or_(
                    func.lower(src_node.label).like(needle),
                    func.lower(dst_node.label).like(needle),
                    func.lower(OntologyEdge.predicate).like(needle),
                ))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            return [
                Triple(src=s_label, predicate=e.predicate, dst=d_label)
                for e, s_label, d_label in rows
            ]


_store: OntologyStore | None = None


def get_ontology() -> OntologyStore:
    global _store
    if _store is None:
        _store = OntologyStore()
    return _store
