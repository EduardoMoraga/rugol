"""Health and version endpoints."""
from __future__ import annotations

import datetime as dt
import os

from fastapi import APIRouter
from sqlalchemy import func, select

from core import __version__
from core.db import async_session_factory
from core.db.models import Agent, Project, Run, Schedule
from core.runner.orchestrator import get_orchestrator

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # Branding por variante (Rugol / Rugol CRM / Rugol HRO). El desktop wrapper
    # inyecta estas env vars; el dashboard las aplica en runtime → un solo build
    # del dashboard sirve a las tres apps.
    return {
        "status": "ok",
        "version": __version__,
        "active_runs": get_orchestrator().active_count,
        "brand": os.environ.get("RUGOL_BRAND_NAME", "Rugol"),
        "accent": os.environ.get("RUGOL_BRAND_ACCENT", ""),
        "accent_strong": os.environ.get("RUGOL_BRAND_ACCENT_STRONG", ""),
        "tagline": os.environ.get("RUGOL_BRAND_TAGLINE", ""),
        "variant": os.environ.get("RUGOL_VARIANT", "rugol"),  # rugol|crm|hro
    }


@router.get("/health/full")
async def health_full() -> dict:
    """Extended health: counts across the schema, last-24h run stats,
    flags whether the user actually has anything real yet (Capa 11)."""
    since = dt.datetime.now(dt.UTC) - dt.timedelta(hours=24)
    async with async_session_factory() as session:
        projects = (await session.execute(select(func.count(Project.id)))).scalar_one()
        named_projects = (await session.execute(
            select(func.count(Project.id)).where(Project.slug != "workspace")
        )).scalar_one()
        agents = (await session.execute(select(func.count(Agent.id)))).scalar_one()
        schedules = (await session.execute(select(func.count(Schedule.id)))).scalar_one()
        runs_24h = (await session.execute(
            select(func.count(Run.id)).where(Run.started_at >= since)
        )).scalar_one()
        cost_24h = (await session.execute(
            select(func.coalesce(func.sum(Run.cost_usd), 0.0)).where(Run.started_at >= since)
        )).scalar_one() or 0.0
        failed_24h = (await session.execute(
            select(func.count(Run.id))
            .where(Run.started_at >= since)
            .where(Run.status == "failed")
        )).scalar_one()
    return {
        "status": "ok",
        "version": __version__,
        "active_runs": get_orchestrator().active_count,
        "schema": {
            "projects_total": int(projects),
            "projects_named": int(named_projects),
            "agents": int(agents),
            "schedules": int(schedules),
        },
        "activity_24h": {
            "runs": int(runs_24h),
            "failed": int(failed_24h),
            "cost_usd": float(cost_24h),
            "failure_rate": (failed_24h / runs_24h) if runs_24h else 0.0,
        },
        "first_use": int(named_projects) == 0,
    }
