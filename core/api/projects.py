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
    job_description: str = ""
    cv_folder: str = ""
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
    job_description: str = ""
    cv_folder: str = ""
    color: str = "#7280a8"
    icon: str = "briefcase"


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    mission: str | None = None
    job_description: str | None = None
    cv_folder: str | None = None
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
        job_description=getattr(p, "job_description", "") or "",
        cv_folder=getattr(p, "cv_folder", "") or "",
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
            job_description=body.job_description.strip(),
            cv_folder=body.cv_folder.strip(),
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
        if body.job_description is not None:
            p.job_description = body.job_description.strip()
        if body.cv_folder is not None:
            p.cv_folder = body.cv_folder.strip()
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


class ScreenBody(BaseModel):
    folder: str | None = None  # si no se pasa, usa el cv_folder de la búsqueda


@router.post("/{id_or_slug}/screen-cvs", status_code=202)
async def screen_cvs(id_or_slug: str, body: ScreenBody) -> dict:
    """Fuente de CVs: dispara al agente screener sobre una carpeta para esta
    búsqueda. El agente lee cada CV, lo evalúa contra la job description y
    registra a los candidatos en el pipeline ligados a la búsqueda."""
    from pathlib import Path as _Path
    from core.runner.orchestrator import RunRequest, get_orchestrator
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="búsqueda no encontrada")
        folder = (body.folder or getattr(p, "cv_folder", "") or "").strip()
        if not folder:
            raise HTTPException(status_code=400, detail="Conecta una carpeta de CVs a esta búsqueda primero.")
        # Validar que la carpeta exista en disco ANTES de gastar una corrida del agente.
        _fp = _Path(folder).expanduser()
        if not _fp.exists():
            raise HTTPException(status_code=400, detail=f"La carpeta «{folder}» no existe. Revisa la ruta en Fuente de CVs.")
        if not _fp.is_dir():
            raise HTTPException(status_code=400, detail=f"«{folder}» no es una carpeta. Conecta una carpeta con los CVs.")
        try:
            _has_files = any(_fp.iterdir())
        except PermissionError:
            raise HTTPException(status_code=400, detail=f"No tengo permiso para leer la carpeta «{folder}».")
        if not _has_files:
            raise HTTPException(status_code=400, detail=f"La carpeta «{folder}» está vacía. Agrega los CVs y vuelve a intentar.")
        jd = (getattr(p, "job_description", "") or p.mission or p.description or p.name).strip()
        slug, name = p.slug, p.name
    prompt = (
        f"Analiza los CVs de la carpeta `{folder}` para la búsqueda «{name}».\n\n"
        f"Perfil del cargo (job description):\n{jd or '(sin descripción; evalúa por idoneidad general)'}\n\n"
        "Pasos:\n"
        "1. Lista los archivos de la carpeta (Bash `ls` o Glob).\n"
        "2. Por cada CV (PDF/DOCX/imagen/texto), ábrelo con tu herramienta Read y evalúalo contra el perfil.\n"
        "3. Asigna un score de encaje 1-5 con evidencia tomada del CV.\n"
        "4. Registra a CADA candidato evaluado en el pipeline con POST al endpoint /api/pipeline: "
        f'kind=\"candidate\", title=<nombre del candidato>, subtitle=<rol o seniority>, stage=\"Screening\", '
        f'score=<1-5>, source_agent=\"hro-screener\", project_slug=\"{slug}\", '
        'note=<una línea de por qué>, y data con {"fortalezas":[...],"banderas":[...],"cv_file":"<nombre archivo>"}.\n'
        "5. No inventes datos: lo que no esté en el CV, no lo afirmes.\n"
        "Al terminar, resume cuántos CVs procesaste y cuántos candidatos registraste."
    )
    try:
        run_id = await get_orchestrator().enqueue(RunRequest(
            agent_name="hro-screener", prompt=prompt, source="dashboard",
        ))
    except ValueError:
        raise HTTPException(status_code=400, detail="No encontré el agente 'hro-screener'. Verifica que exista en Agentes.")
    return {"run_id": run_id, "status": "queued", "folder": folder}


class ConnectBody(BaseModel):
    kind: str = "api"          # api | pandape | drive | onedrive | web | folder
    goal: str                  # qué traer, en lenguaje natural
    credentials: str | None = None  # token/JSON/usuario:clave (se guarda local, no en el prompt)
    target_folder: str | None = None


@router.post("/{id_or_slug}/connect", status_code=202)
async def connect_source(id_or_slug: str, body: ConnectBody) -> dict:
    """Conector: el agente `connector` construye y ejecuta una integración
    (API/Pandapé, Drive/OneDrive, web) y deja los CVs en la carpeta de la
    búsqueda. Las credenciales se guardan en un archivo local (no en el prompt)."""
    import json as _json
    from pathlib import Path as _Path
    from core.config import REPO_ROOT
    from core.runner.orchestrator import RunRequest, get_orchestrator
    async with async_session_factory() as session:
        p = await _resolve(session, id_or_slug)
        if p is None:
            raise HTTPException(status_code=404, detail="búsqueda no encontrada")
        slug, name = p.slug, p.name
        # Carpeta destino: la del proyecto, la indicada, o una gestionada por búsqueda.
        target = (body.target_folder or getattr(p, "cv_folder", "") or "").strip()
        if not target:
            target = str(_Path(REPO_ROOT) / "data" / "cv_sources" / slug)
        _Path(target).mkdir(parents=True, exist_ok=True)
        if not getattr(p, "cv_folder", ""):
            p.cv_folder = target
            await session.commit()
    # Guardar credenciales fuera del prompt (archivo local que el agente lee).
    secrets_path = ""
    if body.credentials and body.credentials.strip():
        cdir = _Path(REPO_ROOT) / "connectors"
        cdir.mkdir(parents=True, exist_ok=True)
        secrets_path = str(cdir / f"{slug}.secret")
        _Path(secrets_path).write_text(body.credentials.strip(), encoding="utf-8")
    prompt = (
        f"Construye y ejecuta una integración para la búsqueda «{name}».\n\n"
        f"Objetivo: {body.goal.strip()}\n"
        f"Tipo de fuente: {body.kind}\n"
        f"Carpeta destino (deja ahí los CVs/archivos): `{target}`\n"
        + (f"Credenciales: están en el archivo `{secrets_path}` — léelas de ahí con Read, NO las imprimas.\n" if secrets_path else "")
        + "\nPasos: arma el flujo (script), ejecútalo, descarga los CVs/datos a la carpeta destino y deja el script guardado para re-ejecutar. "
        "Al terminar, reporta cuántos archivos trajiste y de dónde. Si falta algo (endpoint, credencial), dilo claro."
    )
    try:
        run_id = await get_orchestrator().enqueue(RunRequest(
            agent_name="connector", prompt=prompt, source="dashboard",
        ))
    except ValueError:
        raise HTTPException(status_code=400, detail="No encontré el agente 'connector'. Verifica que exista en Agentes.")
    return {"run_id": run_id, "status": "queued", "target_folder": target}


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
