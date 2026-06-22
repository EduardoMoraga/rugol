"""Runtime settings — what the user toggles from /settings.

GET  /api/settings           → masked public state (no raw secrets)
POST /api/settings           → merge updates, persist, hot-restart adapters
GET  /api/settings/status    → current adapter / watcher health
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core import runtime_state
from core.registry.service import build_watcher, initial_scan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    telegram_bot_token: str | None = None
    telegram_allowed_users: str | None = None
    slack_bot_token: str | None = None
    slack_signing_secret: str | None = None
    slack_app_token: str | None = None
    agents_dir: str | None = None
    skills_dir: str | None = None
    default_model: str | None = None
    elevenlabs_api_key: str | None = None
    elevenlabs_agent_id: str | None = None
    onboarding_done: bool | None = None


@router.get("")
async def get_settings_public() -> dict[str, Any]:
    return runtime_state.load().as_public_dict()


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    """Live status of every subsystem the user can configure."""
    telegram = getattr(request.app.state, "telegram", None)
    slack = getattr(request.app.state, "slack", None)
    watcher = getattr(request.app.state, "watcher", None)
    s = runtime_state.load()
    bots = runtime_state.telegram_bots()
    return {
        "telegram": {
            "configured": bool(bots),
            "running": bool(telegram and getattr(telegram, "_app", None)),
            "bot_count": len(bots),
            "bots": [
                {"key": b["key"], "agent": b["agent"], "label": b["label"]}
                for b in bots
            ],
            "allowed_user_ids": sorted(runtime_state.telegram_allowed_user_ids()),
        },
        "slack": {
            "configured": bool(s.slack_bot_token and s.slack_app_token),
            "running": bool(slack and getattr(slack, "_app", None)),
        },
        "watcher": {
            "agents_dir": str(runtime_state.agents_dir()),
            "skills_dir": str(runtime_state.skills_dir()),
            "running": bool(watcher and getattr(watcher, "_observer", None)),
        },
        "elevenlabs": {
            "configured": bool(runtime_state.elevenlabs_creds()[0] and runtime_state.elevenlabs_creds()[1]),
        },
    }


@router.post("")
async def update_settings(body: SettingsUpdate, request: Request) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}

    # If the user explicitly cleared a token (sent ""), persist that.
    # If a path was set, validate it exists.
    for path_key in ("agents_dir", "skills_dir"):
        if path_key in updates and updates[path_key]:
            p = Path(updates[path_key]).expanduser()
            if not p.exists():
                raise HTTPException(status_code=400, detail=f"{path_key} does not exist: {p}")
            updates[path_key] = str(p.resolve())

    runtime_state.save(updates)

    # Decide what needs a hot restart.
    restart: dict[str, str] = {}

    needs_telegram_restart = any(k in updates for k in ("telegram_bot_token", "telegram_allowed_users"))
    needs_slack_restart = any(
        k in updates for k in ("slack_bot_token", "slack_signing_secret", "slack_app_token")
    )
    needs_watcher_restart = any(k in updates for k in ("agents_dir", "skills_dir"))

    if needs_telegram_restart:
        restart["telegram"] = await _restart_telegram(request)
    if needs_slack_restart:
        restart["slack"] = await _restart_slack(request)
    if needs_watcher_restart:
        restart["watcher"] = await _restart_watcher(request)

    return {
        "ok": True,
        "settings": runtime_state.load().as_public_dict(),
        "restarted": restart,
    }


async def _restart_telegram(request: Request) -> str:
    from core.adapters.telegram import TelegramAdapter
    old = getattr(request.app.state, "telegram", None)
    try:
        if old:
            await old.stop()
    except Exception:
        logger.exception("error stopping old telegram adapter")
    new = TelegramAdapter()
    try:
        await new.start()
    except Exception as e:
        logger.exception("telegram restart failed")
        request.app.state.telegram = new
        return f"failed: {e}"
    request.app.state.telegram = new
    return "ok"


async def _restart_slack(request: Request) -> str:
    from core.adapters.slack import SlackAdapter
    old = getattr(request.app.state, "slack", None)
    try:
        if old:
            await old.stop()
    except Exception:
        logger.exception("error stopping old slack adapter")
    new = SlackAdapter()
    try:
        await new.start()
    except Exception as e:
        logger.exception("slack restart failed")
        request.app.state.slack = new
        return f"failed: {e}"
    request.app.state.slack = new
    return "ok"


async def _restart_watcher(request: Request) -> str:
    import asyncio
    old = getattr(request.app.state, "watcher", None)
    try:
        if old:
            old.stop()
    except Exception:
        logger.exception("error stopping watcher")
    try:
        await initial_scan()
        new = build_watcher()
        new.start(asyncio.get_running_loop())
        request.app.state.watcher = new
        return "ok"
    except Exception as e:
        logger.exception("watcher restart failed")
        return f"failed: {e}"
