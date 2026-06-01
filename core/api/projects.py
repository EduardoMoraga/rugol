"""Projects CRUD — the unit of mental account in Rugol (ADR-005).

Projects group teams of agents around a shared mission. Every agent belongs
to exactly one project (Workspace by default). Deleting a project requires
the user to first move or remove its agents, since orphaning agents silently
hides them from the project-first navigation.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, Project, Run

router = APIRouter(prefix="/projects", tags=["projects"])

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class ProjectDTO(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    mission: str
    color: str
    icon: str
    status: str
    lessons: list[dict] = Field(default_factory=list)
    agent_count: int = 0
    runs_24h: int = 0
    cost_24h: float = 0.0
    created_at: str
    updated_at: str


class LessonAdd(BaseModel):
    text: str = Field(min_length=4, max_length=500)
    kind: Literal["lesson", "bias", "fact"] = "lesson"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    slug: str | None = None  # auto-generated from name when missing
    description: str = ""
    mission: str = ""
    color: str = "#7280a8"
    icon: str = "briefcase"


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    mission: str | None = None
    color: str | None = None
    icon: str | None = None
    status: str | None = None


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s[:80] or "project"


def _validate_slug(slug: str) -> None:
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(
            status_code=400,
            detail="Slug must be lowercase, 3-80 chars, only letters/digits/dashes, no leading/trailing dash.",
        )


def _to_dto(p: Project, agent_count: int, runs_24h: int, cost_24h: float) -> ProjectDTO:
    return ProjectDTO(
        id=p.id,
        slug=p.slug,
        name=p.name,
        description=p.description,
        mission=p.mission,
        color=p.color,
        icon=p.icon,
        status=p.status,
        lessons=list(p.lessons or []),
        agent_count=agent_count,
        runs_24h=runs_24h,
        cost_24h=cost_24h,
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


async def _resolve(session, id_or_slug: str) -> Project | None:
    try:
        pid = int(id_or_slug)
        return await session.get(Project, pid)
    except ValueError:
        return (await session.execute(
            select(Project).where(Project.slug == id_or_slug.lower())
        )).scalar_one_or_none()


async def _aggregate(session, project_id: int) -> tuple[int, int, float]:
    """Returns (agent_count, runs_24h, cost_24h) for a project."""
    agent_count = (await session.execute(
        select(func.count(Agent.id)).where(Agent.project_id == project_id)
    )).scalar_one() or 0
    since = dt.datetime.now(dt.UTC) - dt.timedelta(hours=24)
    runs_q = (
        select(func.count(Run.id), func.coalesce(func.sum(Run.cost_usd), 0.0))
        .join(Agent, Agent.id == Run.agent_id)
        .where(Agent.project_id == project_id)
        .where(Run.started_at >= since)
    )
    runs_24h, cost_24h = (await session.execute(runs_q)).one()
    return int(agent_count), int(runs_24h or 0), float(cost_24h or 0.0)


@router.get("", response_model=list[ProjectDTO])
async def list_projects(include_archived: bool = False) -> list[ProjectDTO]:
    async with async_session_factory() as session:
        stmt = select(Project).order_by(Project.created_at.asc())
        if not include_archived:
            stmt = stmt.where(Project.status == "active")
        projects = (await session.execute(stmt)).scalars().all()
        out: list[ProjectDTO] = []
        for p in projects:
            ac, r24, c24 = await _aggregate(session, p.id)
            out.append(_to_dto(p, ac, r24, c24))
        return out


@router.post("", response_model=ProjectDTO, status_code=201)
async def create_project(body: ProjectCreate) -> ProjectDTO:
    slug = body.slug or _slugify(body.name)
    _validate_slug(slug)
    async with async_session_factory() as session:
        existing = (await session.execute(
            select(Project).where(Project.slug == slug)
        )).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"Project slug already in use: {slug}")
        p = Project(
            slug=slug,
            name=body.name.strip(),
            description=body.description.strip(),
            mission=body.mission.strip(),
            color=body.color.strip() or "#7280a8",
            icon=body.icon.strip() or "briefcase",
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)
        await bus.publish("project:created", {"id": p.id, "slug": p.slug, "name": p.name})
        return _to_dto(p, 0, 0, 0.0)


@router.get("/{id_or_slug}", response_model=ProjectDTO)
async def get_project(id_or_slug: str) -> ProjectDTO:
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        ac, r24, c24 = await _aggregate(session, p.id)
        return _to_dto(p, ac, r24, c24)


@router.patch("/{id_or_slug}", response_model=ProjectDTO)
async def update_project(id_or_slug: str, body: ProjectUpdate) -> ProjectDTO:
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        if body.name is not None:
            p.name = body.name.strip() or p.name
        if body.description is not None:
            p.description = body.description.strip()
        if body.mission is not None:
            p.mission = body.mission.strip()
        if body.color is not None:
            p.color = body.color.strip() or p.color
        if body.icon is not None:
            p.icon = body.icon.strip() or p.icon
        if body.status is not None and body.status in {"active", "archived"}:
            p.status = body.status
        await session.commit()
        ac, r24, c24 = await _aggregate(session, p.id)
        await bus.publish("project:updated", {"id": p.id, "slug": p.slug})
        return _to_dto(p, ac, r24, c24)


@router.delete("/{id_or_slug}", status_code=204)
async def delete_project(id_or_slug: str) -> None:
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        if p.slug == "workspace":
            raise HTTPException(status_code=400, detail="The Workspace project cannot be deleted.")
        ac = (await session.execute(
            select(func.count(Agent.id)).where(Agent.project_id == p.id)
        )).scalar_one() or 0
        if ac:
            raise HTTPException(
                status_code=409,
                detail=f"Project still has {ac} agent(s). Move or delete them first.",
            )
        await session.delete(p)
        await session.commit()
        await bus.publish("project:deleted", {"id": p.id, "slug": p.slug})


@router.get("/{id_or_slug}/agents")
async def list_project_agents(id_or_slug: str) -> list[dict]:
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = (await session.execute(
            select(Agent).where(Agent.project_id == p.id).order_by(Agent.name)
        )).scalars().all()
        return [
            {
                "id": a.id,
                "name": a.name,
                "model": a.model,
                "description": a.description,
                "status": a.status,
                "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            }
            for a in rows
        ]


@router.post("/{id_or_slug}/lessons", response_model=ProjectDTO)
async def add_lesson(id_or_slug: str, body: LessonAdd) -> ProjectDTO:
    """Append a new lesson to the project's living list (Capa 3).

    Lessons are surfaced inside every run's system prompt. They're how the
    project remembers what the team learned the hard way — biases corrected,
    decisions made, domain facts the agents shouldn't have to re-derive.
    """
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        item = {
            "kind": body.kind,
            "text": body.text.strip(),
            "source": "user",
            "added_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        current = list(p.lessons or [])
        current.append(item)
        p.lessons = current
        await session.commit()
        ac, r24, c24 = await _aggregate(session, p.id)
        await bus.publish("project:lesson-added", {"project_slug": p.slug, "kind": body.kind})
        return _to_dto(p, ac, r24, c24)


@router.delete("/{id_or_slug}/lessons/{index}", response_model=ProjectDTO)
async def remove_lesson(id_or_slug: str, index: int) -> ProjectDTO:
    """Remove a lesson by its position in the list."""
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        current = list(p.lessons or [])
        if not (0 <= index < len(current)):
            raise HTTPException(status_code=404, detail="lesson index out of range")
        current.pop(index)
        p.lessons = current
        await session.commit()
        ac, r24, c24 = await _aggregate(session, p.id)
        return _to_dto(p, ac, r24, c24)


@router.get("/{id_or_slug}/runs")
async def list_project_runs(id_or_slug: str, limit: int = 30) -> list[dict]:
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="project not found")
        rows = (await session.execute(
            select(Run, Agent)
            .join(Agent, Agent.id == Run.agent_id)
            .where(Agent.project_id == p.id)
            .order_by(desc(Run.id))
            .limit(limit)
        )).all()
        return [
            {
                "id": r.id,
                "agent_id": a.id,
                "agent_name": a.name,
                "source": r.source,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
                "prompt": (r.prompt or "")[:200],
            }
            for r, a in rows
        ]
