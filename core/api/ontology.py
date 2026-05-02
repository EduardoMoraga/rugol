"""Ontology graph API."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from core.db import async_session_factory
from core.db.models import OntologyEdge, OntologyNode
from core.ontology import get_ontology

router = APIRouter(prefix="/ontology", tags=["ontology"])


class TripleBody(BaseModel):
    src: str
    predicate: str
    dst: str


@router.get("/nodes")
async def list_nodes(limit: int = 200) -> list[dict]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(OntologyNode).limit(limit))).scalars().all()
        return [{"id": n.id, "label": n.label, "type": n.type, "meta": n.meta} for n in rows]


@router.get("/edges")
async def list_edges(limit: int = 500) -> list[dict]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(OntologyEdge).limit(limit))).scalars().all()
        return [{"id": e.id, "src": e.src, "predicate": e.predicate, "dst": e.dst, "weight": e.weight} for e in rows]


@router.post("/triples", status_code=201)
async def add_triple(body: TripleBody) -> dict:
    edge_id = await get_ontology().add_edge(body.src, body.predicate, body.dst)
    return {"edge_id": edge_id}


@router.get("/neighbors/{label}")
async def neighbors(label: str, predicate: str | None = None) -> list[dict]:
    triples = await get_ontology().neighbors(label, predicate)
    return [{"src": t.src, "predicate": t.predicate, "dst": t.dst} for t in triples]
