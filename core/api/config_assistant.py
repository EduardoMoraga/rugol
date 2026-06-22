"""Config Assistant API — paste-and-go config from arbitrary user input.

Endpoints:
- POST /config-assistant/parse   — parse input, return public (token-masked) plan + a token to apply
- POST /config-assistant/apply   — apply selected actions from a previously parsed plan

The full plan (with raw secrets) lives in an in-memory cache keyed by a
short-lived plan_token so we never round-trip secrets through the
client. The cache expires in 10 minutes.
"""
from __future__ import annotations

import logging
import secrets as _secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config_assistant import (
    ConfigPlan,
    apply_plan,
    parse_user_input,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config-assistant", tags=["config-assistant"])


# In-memory plan cache (plan_token → (created_ts, ConfigPlan)).
# Trim entries older than 10 minutes on each access.
_PLAN_CACHE: dict[str, tuple[float, ConfigPlan]] = {}
_PLAN_TTL_S = 600.0


def _gc_cache() -> None:
    cutoff = time.time() - _PLAN_TTL_S
    expired = [k for k, (ts, _) in _PLAN_CACHE.items() if ts < cutoff]
    for k in expired:
        _PLAN_CACHE.pop(k, None)


class ParseBody(BaseModel):
    text: str


class ApplyBody(BaseModel):
    plan_token: str
    action_ids: list[str]


@router.post("/parse")
async def parse(body: ParseBody) -> dict[str, Any]:
    _gc_cache()
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")
    try:
        plan = await parse_user_input(body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("config-assistant parse failed")
        raise HTTPException(
            status_code=500,
            detail="No pude interpretar el texto. Revisa que contenga una configuración válida (tokens, claves) e intenta de nuevo.",
        )

    plan_token = _secrets.token_urlsafe(16)
    _PLAN_CACHE[plan_token] = (time.time(), plan)
    return {
        "plan_token": plan_token,
        "plan": plan.as_public_dict(),
        "ttl_seconds": int(_PLAN_TTL_S),
    }


@router.post("/apply")
async def apply(body: ApplyBody) -> dict[str, Any]:
    _gc_cache()
    cached = _PLAN_CACHE.get(body.plan_token)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="Plan no encontrado o expirado. Vuelve a analizar el input.",
        )
    _, plan = cached
    selected = set(body.action_ids)
    if not selected:
        raise HTTPException(status_code=400, detail="No seleccionaste ninguna acción.")
    try:
        outcome = await apply_plan(plan, selected)
    except Exception:
        logger.exception("config-assistant apply failed")
        raise HTTPException(
            status_code=500,
            detail="No se pudo aplicar la configuración. Revisa los datos e intenta de nuevo.",
        )
    # Once applied, drop the plan from cache to prevent reuse.
    _PLAN_CACHE.pop(body.plan_token, None)
    return outcome
