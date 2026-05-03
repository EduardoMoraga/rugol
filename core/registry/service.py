"""Glue between watcher, parser and DB upsert."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select

from core import runtime_state
from core.bus import bus
from core.config import get_settings
from core.db import async_session_factory
from core.db.models import Agent, Project, Skill
from core.registry.loader import load_agent_file, load_skill_file
from core.registry.watcher import RegistryWatcher

logger = logging.getLogger(__name__)


async def _resolve_project_id(session, parsed_slug: str | None) -> int | None:
    """Map a frontmatter `project:` slug to a project row id.

    Falls back to the Workspace project when the slug is unknown or missing.
    Never auto-creates a project from an unknown slug — that has to be an
    explicit user action (ADR-005). Returns None only if even Workspace is
    missing, which should not happen after _ensure_workspace_project().
    """
    if parsed_slug:
        row = (await session.execute(
            select(Project).where(Project.slug == parsed_slug)
        )).scalar_one_or_none()
        if row is not None:
            return row.id
        logger.warning(
            "agent references unknown project slug %r — falling back to Workspace",
            parsed_slug,
        )
    ws = (await session.execute(
        select(Project).where(Project.slug == "workspace")
    )).scalar_one_or_none()
    return ws.id if ws else None


async def upsert_agent_file(path: Path) -> None:
    if not path.exists() or path.suffix != ".md":
        return
    parsed = load_agent_file(path, default_model=runtime_state.default_model())
    async with async_session_factory() as session:
        existing = (await session.execute(
            select(Agent).where(Agent.name == parsed.name)
        )).scalar_one_or_none()
        project_id = await _resolve_project_id(session, parsed.project_slug)
        if existing is None:
            row = Agent(
                name=parsed.name, model=parsed.model, description=parsed.description,
                body=parsed.body, source_path=parsed.source_path, body_hash=parsed.body_hash,
                status="idle", project_id=project_id,
            )
            session.add(row)
            await session.commit()
            await bus.publish("agent:registered", {"name": parsed.name})
        elif existing.body_hash != parsed.body_hash or existing.project_id != project_id:
            existing.model = parsed.model
            existing.description = parsed.description
            existing.body = parsed.body
            existing.body_hash = parsed.body_hash
            existing.source_path = parsed.source_path
            if project_id is not None:
                existing.project_id = project_id
            await session.commit()
            await bus.publish("agent:updated", {"name": parsed.name})
    logger.info("agent upserted: %s", parsed.name)


async def upsert_skill_file(path: Path) -> None:
    if not path.exists() or path.suffix != ".md":
        return
    parsed = load_skill_file(path)
    async with async_session_factory() as session:
        existing = (await session.execute(
            select(Skill).where(Skill.name == parsed.name)
        )).scalar_one_or_none()
        if existing is None:
            row = Skill(
                name=parsed.name, description=parsed.description, body=parsed.body,
                source_path=parsed.source_path, body_hash=parsed.body_hash,
            )
            session.add(row)
            await session.commit()
            await bus.publish("skill:registered", {"name": parsed.name})
        elif existing.body_hash != parsed.body_hash:
            existing.description = parsed.description
            existing.body = parsed.body
            existing.body_hash = parsed.body_hash
            existing.source_path = parsed.source_path
            await session.commit()
            await bus.publish("skill:updated", {"name": parsed.name})


async def initial_scan() -> None:
    """Walk the configured agents/skills folders at startup or on hot reload."""
    agents_dir = runtime_state.agents_dir()
    skills_dir = runtime_state.skills_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    for path in agents_dir.rglob("*.md"):
        await upsert_agent_file(path)
    for path in skills_dir.rglob("*.md"):
        await upsert_skill_file(path)


def build_watcher() -> RegistryWatcher:
    return RegistryWatcher(
        agents_dir=runtime_state.agents_dir(),
        skills_dir=runtime_state.skills_dir(),
        on_agent=upsert_agent_file,
        on_skill=upsert_skill_file,
    )
