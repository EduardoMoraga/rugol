"""Take a (possibly user-edited) Proposal and make it real on disk + DB."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

import re

from core import runtime_state
from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, Project, Schedule
from core.ontology import get_ontology
from core.registry.service import upsert_agent_file, upsert_skill_file
from core.scheduler import get_scheduler
from sqlalchemy import select

from .proposer import Proposal, ProposalProject

logger = logging.getLogger(__name__)


@dataclass
class DeployResult:
    project_slug: str | None = None
    project_id: int | None = None
    project_created: bool = False
    agents_created: list[str] = field(default_factory=list)
    agents_skipped: list[dict] = field(default_factory=list)
    skills_created: list[str] = field(default_factory=list)
    skills_skipped: list[dict] = field(default_factory=list)
    schedules_created: list[int] = field(default_factory=list)
    schedules_skipped: list[dict] = field(default_factory=list)
    ontology_edges_created: int = 0

    def as_dict(self) -> dict:
        return self.__dict__


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s[:80] or "project"


def _agent_md(name: str, model: str, description: str, body: str, project_slug: str | None) -> str:
    esc = description.replace('"', '\\"')
    lines = ["---", f"name: {name}", f"model: {model}"]
    if project_slug:
        lines.append(f"project: {project_slug}")
    lines.append(f'description: "{esc}"')
    lines.append("---\n")
    return "\n".join(lines) + "\n" + body.strip() + "\n"


async def _ensure_project(spec: ProposalProject | None) -> tuple[Project, bool]:
    """Resolve the project for a deploy: create new, reuse by slug, or fall back to Workspace.

    Returns the Project row and a boolean indicating whether it was created.
    The Workspace project is never reported as "created" here.
    """
    async with async_session_factory() as session:
        if spec is None or not spec.name:
            ws = (await session.execute(
                select(Project).where(Project.slug == "workspace")
            )).scalar_one()
            return ws, False
        slug = (spec.slug or _slugify(spec.name)).strip().lower()
        existing = (await session.execute(
            select(Project).where(Project.slug == slug)
        )).scalar_one_or_none()
        if existing is not None:
            return existing, False
        proj = Project(
            slug=slug,
            name=spec.name.strip(),
            description=spec.description.strip(),
            mission=spec.mission.strip(),
            color=(spec.color or "#7280a8").strip(),
            icon=(spec.icon or "briefcase").strip(),
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        await bus.publish("project:created", {"id": proj.id, "slug": proj.slug, "name": proj.name, "via": "architect"})
        return proj, True


def _skill_md(name: str, description: str, body: str) -> str:
    esc = description.replace('"', '\\"')
    return (
        "---\n"
        f"name: {name}\n"
        f'description: "{esc}"\n'
        "---\n\n"
        + body.strip() + "\n"
    )


async def deploy(
    proposal: Proposal,
    target_agents_dir = None,
    target_skills_dir = None,
) -> DeployResult:
    """Materialize the proposal: write .md files, register schedules, seed
    the ontology, ensure the project exists.

    `target_agents_dir` and `target_skills_dir` (Path or None) override the
    global install location for *this* deploy only. Useful when the user
    wants a project's files to live in a specific folder without touching
    the global settings.
    """
    res = DeployResult()
    agents_dir = target_agents_dir or runtime_state.agents_dir()
    skills_dir = target_skills_dir or runtime_state.skills_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    # 0. Project — every deploy lands inside one project (ADR-005).
    project, created = await _ensure_project(proposal.project)
    res.project_slug = project.slug
    res.project_id = project.id
    res.project_created = created

    # 1. Agents
    for a in proposal.agents:
        target = agents_dir / f"{a.name}.md"
        if target.exists():
            res.agents_skipped.append({"name": a.name, "reason": "file already exists"})
            continue
        target.write_text(
            _agent_md(a.name, a.model, a.description, a.body, project.slug),
            encoding="utf-8",
        )
        await upsert_agent_file(target)
        res.agents_created.append(a.name)

    # 2. Skills
    for s in proposal.skills:
        target = skills_dir / f"{s.name}.md"
        if target.exists():
            res.skills_skipped.append({"name": s.name, "reason": "file already exists"})
            continue
        target.write_text(_skill_md(s.name, s.description, s.body), encoding="utf-8")
        await upsert_skill_file(target)
        res.skills_created.append(s.name)

    # 3. Schedules — need agent IDs from the DB.
    if proposal.schedules:
        scheduler = get_scheduler()
        async with async_session_factory() as session:
            for sch in proposal.schedules:
                agent_row = (await session.execute(
                    select(Agent).where(Agent.name == sch.agent_name)
                )).scalar_one_or_none()
                if agent_row is None:
                    res.schedules_skipped.append({
                        "agent_name": sch.agent_name,
                        "reason": "agent does not exist (was it skipped?)",
                    })
                    continue
                row = Schedule(
                    agent_id=agent_row.id,
                    cron_expr=sch.cron_expr,
                    prompt=sch.prompt,
                    enabled=True,
                )
                session.add(row)
                await session.flush()
                schedule_id = row.id
                try:
                    scheduler.add_cron(schedule_id, agent_row.name, sch.prompt, sch.cron_expr)
                except Exception as e:
                    res.schedules_skipped.append({
                        "agent_name": sch.agent_name,
                        "reason": f"invalid cron: {e}",
                    })
                    await session.rollback()
                    continue
                await session.commit()
                res.schedules_created.append(schedule_id)

    # 4. Ontology seeds
    if proposal.ontology_seeds:
        store = get_ontology()
        for triple in proposal.ontology_seeds:
            try:
                await store.add_edge(triple.src, triple.predicate, triple.dst)
                res.ontology_edges_created += 1
            except Exception:
                logger.exception("failed to add seed triple %s", triple)

    await bus.publish("architect:deployed", res.as_dict())
    return res
