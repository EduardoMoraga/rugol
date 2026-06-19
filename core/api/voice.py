"""API de la integración de entrevistas de voz (ElevenLabs "Sofía").

Endpoints (montados bajo /api):
  GET  /api/voice/status         → si la key/agent están configurados + última sync
  GET  /api/voice/conversations  → lista cruda de conversaciones de ElevenLabs
  POST /api/voice/sync           → corre sync_interviews y devuelve el resumen

La api_key/agent_id se leen de settings (ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID),
que a su vez caen a las variables de entorno del mismo nombre.
"""
from __future__ import annotations

import datetime as dt
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.config import get_settings
from core.voice import elevenlabs
from core.voice.sync import sync_interviews

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# Memoria liviana de la última sync (no persiste entre reinicios; el estado
# real de los candidatos vive en el pipeline).
_LAST_SYNC: dict | None = None


def _creds() -> tuple[str, str]:
    # Prioriza lo configurado desde el dashboard (settings.json); cae a env.
    from core import runtime_state
    return runtime_state.elevenlabs_creds()


@router.get("/status")
async def voice_status() -> dict:
    api_key, agent_id = _creds()
    return {
        "configured": bool(api_key and agent_id),
        "has_api_key": bool(api_key),
        "agent_id": agent_id or None,
        "last_sync": _LAST_SYNC,
    }


@router.get("/conversations")
async def voice_conversations(page_size: int = Query(30, ge=1, le=100)) -> dict:
    api_key, agent_id = _creds()
    if not api_key or not agent_id:
        raise HTTPException(503, "ElevenLabs no configurado (falta ELEVENLABS_API_KEY/ELEVENLABS_AGENT_ID)")
    try:
        conversations = elevenlabs.list_conversations(api_key, agent_id, page_size=page_size)
    except Exception as e:  # noqa: BLE001
        logger.exception("voice: list_conversations falló")
        raise HTTPException(502, f"Error consultando ElevenLabs: {e}") from e
    return {
        "agent_id": agent_id,
        "count": len(conversations),
        "conversations": conversations,
    }


class SyncBody(BaseModel):
    limit: int | None = None


@router.post("/sync")
async def voice_sync(body: SyncBody | None = None) -> dict:
    global _LAST_SYNC
    api_key, agent_id = _creds()
    if not api_key or not agent_id:
        raise HTTPException(503, "ElevenLabs no configurado (falta ELEVENLABS_API_KEY/ELEVENLABS_AGENT_ID)")
    limit = body.limit if body else None
    result = await sync_interviews(limit=limit)
    _LAST_SYNC = {
        "at": dt.datetime.now(dt.UTC).isoformat(),
        "processed": result.get("processed"),
        "created": result.get("created"),
        "skipped": result.get("skipped"),
        "errors": len(result.get("errors") or []),
    }
    return result
