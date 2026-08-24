"""Health and version endpoints."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

from fastapi import APIRouter
from sqlalchemy import func, select

from core import __version__, llm_models
from core.db import async_session_factory
from core.db.models import Agent, Project, Run, Schedule
from core.resilience import last_report
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
        # Qué encontró la recuperación de arranque (core/resilience). Después de
        # un corte de luz esto es lo primero que hay que mirar.
        "recovery": (rep.as_dict() if (rep := last_report()) else None),
    }


@router.get("/health/auth")
async def health_auth(refresh: bool = False, verify: bool = False) -> dict:
    """Is the Claude account connected? (the check `doctor` used to fake)

    Two levels, because they cost different things:

    - default: what credential the CLI is configured with, on the very binary a
      run would spawn and with the very environment a run would get. Cheap
      (~1s, cached), safe to poll.
    - `?verify=true`: a real minimal round trip to the API. The only honest
      answer to "does this credential still work" — `claude auth status` reports
      a revoked token as logged in. Costs a fraction of a cent, so it runs only
      when asked.

    Never 500s — when auth is broken this endpoint is how the user finds out.
    """
    from core.runner.claude_cli import auth_status_cached, verify_credentials

    status = await asyncio.to_thread(auth_status_cached, refresh=refresh)
    payload = dict(status)
    ok = bool(status["logged_in"])

    if verify:
        probe = await asyncio.to_thread(verify_credentials)
        payload.update(probe)
        ok = ok and bool(probe["verified"])
    else:
        payload.update({"verified": None, "verify_error": "", "verify_status": None})

    payload["ok"] = ok
    payload["hint"] = _auth_hint(payload)
    return payload


def _auth_hint(status: dict) -> str:
    """One actionable sentence — what to type next, not what went wrong."""
    if not status.get("cli_path"):
        return "Corré `rugol update` para reinstalar las dependencias del backend."
    if not status["logged_in"]:
        return "Corré `rugol login` en esta máquina para conectar tu cuenta de Claude."
    if status.get("verified") is False:
        if status.get("verify_status") == 401:
            return (
                "La credencial existe pero el API la rechazó (401): está vencida o "
                "revocada. Corré `rugol login` para reconectar."
            )
        return "El API rechazó la credencial. Corré `rugol login` para reconectar."
    if status.get("verified") is None:
        # Configurada, sin comprobar. No prometemos que funcione.
        return ""
    return ""


@router.get("/health/engines")
async def health_engines(verify: bool = False) -> dict:
    """Estado de los dos motores, para la pantalla de configuración.

    Lo que el dashboard necesita saber de cada uno: si el CLI está instalado, si
    la cuenta está conectada, y qué comando lo arregla si no. Sin esto el motor
    Codex existía sólo en el frontmatter de un archivo — invisible.
    """
    from core.runner.claude_cli import auth_status_cached, verify_credentials
    from core.runner.codex_runner import auth_status as codex_auth
    from core.runner.codex_runner import find_codex

    claude = await asyncio.to_thread(auth_status_cached, refresh=verify)
    claude_entry = {
        "name": "claude",
        "label": "Claude (Anthropic)",
        "installed": bool(claude["cli_path"]),
        "cli_version": claude["cli_version"],
        "connected": bool(claude["logged_in"]),
        "account": claude["account"],
        "plan": claude["plan"],
        "method": claude["method"],
        "credential_source": claude["credential_source"],
        "verified": None,
        "error": claude["error"],
        "connect_command": "rugol login",
        "install_command": "",
        "default": True,
        "supports_memory": True,
        "missing": [],
        "models": [
            {"value": v, "label": lbl}
            for v, lbl in llm_models.ENGINE_MODEL_CHOICES["claude"]
        ],
        "default_model": llm_models.ENGINE_DEFAULT_MODEL["claude"],
    }
    if verify and claude["logged_in"]:
        probe = await asyncio.to_thread(verify_credentials)
        claude_entry["verified"] = probe["verified"]
        if not probe["verified"]:
            claude_entry["error"] = probe["verify_error"]

    codex = await asyncio.to_thread(codex_auth)
    codex_entry = {
        "name": "codex",
        "label": "Codex (OpenAI)",
        "installed": bool(codex["cli_path"]),
        "cli_version": codex["cli_version"],
        "connected": bool(codex["logged_in"]),
        "account": "",
        "plan": "",
        "method": codex["method"],
        "credential_source": codex["method"],
        "verified": None,
        "error": codex["error"],
        "connect_command": "rugol login --codex",
        "install_command": "" if find_codex() else "npm install -g @openai/codex",
        "default": False,
        # 2.0: la memoria salió de los motores. Se sirve por MCP sobre HTTP y
        # Codex la consume igual que Claude — verificado de punta a punta. Lo
        # que este motor NO tiene son las tools in-process de Telegram.
        "supports_memory": True,
        "missing": ["tools de Telegram (mandar mensajes desde el agente)"],
        "models": [
            {"value": v, "label": lbl}
            for v, lbl in llm_models.ENGINE_MODEL_CHOICES["codex"]
        ],
        "default_model": llm_models.ENGINE_DEFAULT_MODEL["codex"],
    }

    return {"engines": [claude_entry, codex_entry]}
