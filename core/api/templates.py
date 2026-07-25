"""Curated project templates (Capa 6).

GET /api/templates                — list cards
GET /api/templates/{id}           — full payload (for preview)
POST /api/templates/{id}/clone    — deploy as a new project (one click)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from core.architect.deployer import deploy as deploy_proposal
from core.db import async_session_factory
from core.db.models import Project
from core.templates import CATALOG, get_template

router = APIRouter(prefix="/templates", tags=["templates"])


class CloneBody(BaseModel):
    # If the user already has a project with this slug, optionally provide an
    # alternative slug for the clone (Templates have stable slugs, but the
    # user can clone the same template twice with a renamed copy).
    slug_override: str | None = None
    # Same dir override semantics as Architect (Capa 5).
    target_agents_dir: str | None = None
    target_skills_dir: str | None = None


# Templates relevantes por variante. Para HRO/CRM NO mostramos los proyectos
# genéricos (Sesgo Útil, Marca personal, etc.) — solo lo del dominio. Rugol
# (None) muestra todo el catálogo.
_VARIANT_TEMPLATE_IDS: dict[str, set[str]] = {
    "crm": {"pipeline-comercial"},
    "hro": {"reclutamiento"},  # template de reclutamiento (se siembra en el catálogo)
}


def _norm_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "es"


@router.get("")
async def list_templates(lang: str | None = None) -> list[dict]:
    variant = os.environ.get("RUGOL_VARIANT", "rugol")
    allowed = _VARIANT_TEMPLATE_IDS.get(variant)  # None en rugol → todo
    lg = _norm_lang(lang)
    cards = [t.to_card_dict(lg) for t in CATALOG]
    if allowed is not None:
        cards = [c for c in cards if c["id"] in allowed]
    return cards


@router.get("/{template_id}")
async def get_one(template_id: str, lang: str | None = None) -> dict:
    t = get_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="template not found")
    return t.to_full_dict(_norm_lang(lang))


@router.post("/{template_id}/clone")
async def clone(template_id: str, body: CloneBody) -> dict:
    t = get_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="template not found")

    proposal = t.proposal
    if body.slug_override and proposal.project:
        # Build a deep copy with the slug override AND auto-suffix every
        # agent/schedule so the second clone of the same template doesn't
        # collide on agent .md filenames. Suffix = the trailing chunk of
        # the override that differs from the original slug (e.g. "-2").
        from dataclasses import replace
        new_slug = body.slug_override.strip().lower()
        original_slug = proposal.project.slug
        suffix = ""
        if new_slug.startswith(f"{original_slug}-"):
            suffix = new_slug[len(original_slug):]   # "-2", "-clone", etc.
        elif new_slug != original_slug:
            suffix = f"-{new_slug}"
        # Rename agents so .md filenames don't collide with the first clone.
        renamed_agents = []
        rename_map: dict[str, str] = {}
        for a in proposal.agents:
            new_name = f"{a.name}{suffix}" if suffix else a.name
            renamed_agents.append(replace(a, name=new_name))
            rename_map[a.name] = new_name
        # Schedules reference agents by name — keep them in sync.
        renamed_schedules = [
            replace(s, agent_name=rename_map.get(s.agent_name, s.agent_name))
            for s in proposal.schedules
        ]
        new_project = replace(proposal.project, slug=new_slug)
        proposal = replace(
            proposal,
            project=new_project,
            agents=renamed_agents,
            schedules=renamed_schedules,
        )

    # If the destination slug already exists, refuse rather than collide
    # silently — the user picked a clone, not a merge.
    if proposal.project:
        async with async_session_factory() as session:
            existing = (await session.execute(
                select(Project).where(Project.slug == proposal.project.slug)
            )).scalar_one_or_none()
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Ya existe un proyecto con slug '{proposal.project.slug}'. "
                        "Pasá un slug_override en el body para crear una copia con otro nombre."
                    ),
                )

    target_agents = Path(body.target_agents_dir) if body.target_agents_dir else None
    target_skills = Path(body.target_skills_dir) if body.target_skills_dir else None
    res = await deploy_proposal(
        proposal,
        target_agents_dir=target_agents,
        target_skills_dir=target_skills,
    )
    return res.as_dict()
