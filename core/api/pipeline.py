"""Pipeline de dominio: prospectos (CRM) y candidatos (HRO).

Los agentes de la variante (crm-hunter/strategist, hro-screener/matcher) registran
y mueven items vía esta API — tienen Bash+curl y el system prompt les indica usar
http://127.0.0.1:<port>/api. El dashboard lo muestra como kanban. Así el usuario
ve la "actividad registrada": leads/candidatos moviéndose por etapas con notas.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from core.db import async_session_factory
from core.db.models import PipelineItem

router = APIRouter()

STAGES: dict[str, list[str]] = {
    "lead": ["Nuevo", "Contactado", "Respondió", "Calificado", "Reunión", "Cerrado"],
    "candidate": ["Postulado", "Screening", "Entrevista", "Terna", "Oferta", "Contratado"],
}


def _ser(it: PipelineItem) -> dict:
    return {
        "id": it.id,
        "kind": it.kind,
        "title": it.title,
        "subtitle": it.subtitle,
        "stage": it.stage,
        "score": it.score,
        "source_agent": it.source_agent,
        "project_slug": it.project_slug,
        "notes": it.notes or [],
        "data": it.data or {},
        "created_at": it.created_at.isoformat() if it.created_at else None,
        "updated_at": it.updated_at.isoformat() if it.updated_at else None,
    }


@router.get("/pipeline/stages")
def pipeline_stages(kind: str = "lead") -> dict:
    return {"kind": kind, "stages": STAGES.get(kind, STAGES["lead"])}


@router.get("/pipeline")
async def list_pipeline(kind: str | None = None, project: str | None = None, q: str | None = None) -> list[dict]:
    async with async_session_factory() as s:
        query = select(PipelineItem).order_by(PipelineItem.updated_at.desc())
        if kind:
            query = query.where(PipelineItem.kind == kind)
        if project:
            query = query.where(PipelineItem.project_slug == project)
        rows = (await s.execute(query)).scalars().all()
    items = [_ser(r) for r in rows]
    if q:  # búsqueda libre por nombre/subtítulo
        ql = q.strip().lower()
        items = [i for i in items if ql in (i["title"] or "").lower() or ql in (i.get("subtitle") or "").lower()]
    return items


def _rank_score(item: dict) -> float:
    """Puntaje compuesto para recomendar: prioriza la entrevista (BARS 0-100),
    cae al score de screening (1-5→0-100), y ajusta por veredicto."""
    data = item.get("data") or {}
    interview = data.get("interview") or {}
    overall = interview.get("overall")
    base = 0.0
    if isinstance(overall, (int, float)):
        base = float(overall)
    elif isinstance(item.get("score"), int):
        base = float(item["score"]) * 20.0
    verdict = interview.get("verdict")
    if verdict == "avanzar":
        base += 8
    elif verdict == "descartar":
        base -= 15
    return base


def _why(item: dict) -> str:
    """Una línea de por qué se recomienda (para que la reclutadora decida)."""
    data = item.get("data") or {}
    interview = data.get("interview") or {}
    parts: list[str] = []
    overall = interview.get("overall")
    verdict = interview.get("verdict")
    if isinstance(overall, (int, float)):
        v = f" ({verdict})" if verdict else ""
        parts.append(f"Entrevista {int(overall)}/100{v}")
    elif item.get("score"):
        parts.append(f"Screening {item['score']}/5")
    elif item.get("stage"):
        parts.append(item["stage"])
    strengths = data.get("strengths") or data.get("fortalezas") or []
    if isinstance(strengths, list) and strengths:
        parts.append(", ".join(str(x) for x in strengths[:2]))
    return " · ".join(parts)


@router.get("/pipeline/recommend")
async def recommend_candidates(
    q: str | None = None, project: str | None = None, limit: int = 5
) -> list[dict]:
    """Banco de talento: recomienda candidatos del pipeline para una posición.
    Rankea por última entrevista (BARS) + score de screening. `q` busca en
    nombre/subtítulo/fortalezas/notas (sirve incluso para búsquedas de otros
    proyectos: reaprovecha candidatos calificados)."""
    async with async_session_factory() as s:
        query = select(PipelineItem).where(PipelineItem.kind == "candidate")
        if project:
            query = query.where(PipelineItem.project_slug == project)
        rows = (await s.execute(query)).scalars().all()
    items = [_ser(r) for r in rows]

    if q:
        ql = q.strip().lower()

        def _matches(i: dict) -> bool:
            hay = " ".join([
                i.get("title") or "",
                i.get("subtitle") or "",
                " ".join(str(x) for x in ((i.get("data") or {}).get("strengths") or (i.get("data") or {}).get("fortalezas") or [])),
                " ".join(str(n.get("text", "")) for n in (i.get("notes") or [])),
            ]).lower()
            return ql in hay
        items = [i for i in items if _matches(i)]

    ranked = sorted(items, key=_rank_score, reverse=True)[: max(1, min(limit, 50))]
    return [{**i, "rank_score": round(_rank_score(i), 1), "why": _why(i)} for i in ranked]


class CreateBody(BaseModel):
    kind: str
    title: str
    subtitle: str | None = None
    stage: str | None = None
    score: int | None = None
    source_agent: str | None = None
    project_slug: str | None = None
    data: dict = {}
    note: str | None = None


@router.post("/pipeline", status_code=201)
async def create_pipeline(body: CreateBody) -> dict:
    if body.kind not in STAGES:
        raise HTTPException(422, f"kind inválido (usa: {', '.join(STAGES)})")
    stage = body.stage or STAGES[body.kind][0]
    if stage not in STAGES[body.kind]:
        stage = STAGES[body.kind][0]
    notes = []
    if body.note:
        notes.append({"at": dt.datetime.now(dt.UTC).isoformat(), "agent": body.source_agent, "text": body.note})
    async with async_session_factory() as s:
        it = PipelineItem(
            kind=body.kind, title=body.title[:200], subtitle=(body.subtitle or None),
            stage=stage, score=body.score, source_agent=body.source_agent,
            project_slug=(body.project_slug or None),
            notes=notes, data=body.data or {},
        )
        s.add(it)
        await s.commit()
        await s.refresh(it)
        return _ser(it)


class UpdateBody(BaseModel):
    stage: str | None = None
    score: int | None = None
    title: str | None = None
    subtitle: str | None = None
    project_slug: str | None = None
    data: dict | None = None
    note: str | None = None
    note_agent: str | None = None


@router.patch("/pipeline/{item_id}")
async def update_pipeline(item_id: int, body: UpdateBody) -> dict:
    async with async_session_factory() as s:
        it = (await s.execute(select(PipelineItem).where(PipelineItem.id == item_id))).scalar_one_or_none()
        if not it:
            raise HTTPException(404, "item no encontrado")
        if body.stage is not None:
            if body.stage not in STAGES.get(it.kind, []):
                raise HTTPException(422, "stage inválido para este kind")
            it.stage = body.stage
        if body.score is not None:
            it.score = body.score
        if body.title is not None:
            it.title = body.title[:200]
        if body.subtitle is not None:
            it.subtitle = body.subtitle
        if body.project_slug is not None:
            it.project_slug = body.project_slug or None
        if body.data is not None:
            it.data = {**(it.data or {}), **body.data}
        if body.note:
            notes = list(it.notes or [])
            notes.append({"at": dt.datetime.now(dt.UTC).isoformat(), "agent": body.note_agent, "text": body.note})
            it.notes = notes
        await s.commit()
        await s.refresh(it)
        return _ser(it)


@router.delete("/pipeline/{item_id}", status_code=204)
async def delete_pipeline(item_id: int) -> None:
    async with async_session_factory() as s:
        it = (await s.execute(select(PipelineItem).where(PipelineItem.id == item_id))).scalar_one_or_none()
        if it:
            await s.delete(it)
            await s.commit()
