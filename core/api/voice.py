"""API de la integración de entrevistas de voz (ElevenLabs "Sofía").

Endpoints (montados bajo /api):
  GET  /api/voice/status         → si la key/agent están configurados + última sync
  GET  /api/voice/conversations  → lista cruda de conversaciones de ElevenLabs
  POST /api/voice/sync           → corre sync_interviews y devuelve el resumen

La api_key/agent_id se leen de settings (ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID),
que a su vez caen a las variables de entorno del mismo nombre.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.config import get_settings
from core.voice import elevenlabs
from core.voice.sync import sync_interviews
from core.voice.voice_scorer import score_transcript
from core.voice.sync import _upsert_candidate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# Memoria liviana de la última sync (no persiste entre reinicios; el estado
# real de los candidatos vive en el pipeline).
_LAST_SYNC: dict | None = None

# Evita sincronizaciones concurrentes: el scoring BARS es caro (30-60s por
# entrevista) y dos corridas en paralelo duplicarían trabajo y costo.
_SYNC_LOCK = asyncio.Lock()


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
    if _SYNC_LOCK.locked():
        raise HTTPException(429, "Ya hay una sincronización de entrevistas en curso. Espera a que termine.")
    limit = body.limit if body else None
    async with _SYNC_LOCK:
        result = await sync_interviews(limit=limit)
    _LAST_SYNC = {
        "at": dt.datetime.now(dt.UTC).isoformat(),
        "processed": result.get("processed"),
        "created": result.get("created"),
        "skipped": result.get("skipped"),
        "errors": len(result.get("errors") or []),
    }
    return result


class Turn(BaseModel):
    role: str   # "sofia" | "candidate" (el rol importa para el scorer)
    text: str


class ScoreTextBody(BaseModel):
    title: str                       # nombre del candidato
    subtitle: str | None = None      # rol / seniority
    project_slug: str | None = None  # búsqueda a la que se liga
    turns: list[Turn]


@router.post("/score-text")
async def score_text_interview(body: ScoreTextBody) -> dict:
    """Entrevista in-app: puntúa una transcripción de TEXTO con el instrumento
    BARS (misma metodología que Sofía por voz) y registra al candidato en el
    pipeline. NO requiere ElevenLabs — Sofía vive dentro de la app.

    El frontend conduce la conversación con el agente hro-sofia y, al cerrar,
    manda los turnos aquí. Devuelve el item del pipeline y el resumen.
    """
    import uuid

    name = (body.title or "").strip()
    if not name:
        raise HTTPException(400, "Falta el nombre del candidato.")
    cand_turns = [t for t in body.turns if (t.role or "").lower().startswith("cand")]
    if not cand_turns or sum(len(t.text.strip()) for t in cand_turns) < 40:
        raise HTTPException(
            400,
            "La entrevista es muy corta para evaluar. Necesito al menos un par de respuestas del candidato.",
        )

    transcript = {
        "candidate": {"name": name, "position": (body.subtitle or "").strip() or None},
        "turns": [{"role": t.role, "text": t.text} for t in body.turns],
        "date": dt.date.today().isoformat(),
        "source": "in-app",
    }
    try:
        scorecard = await score_transcript(transcript)
    except Exception as e:  # noqa: BLE001
        logger.exception("voice: score-text falló")
        raise HTTPException(
            502,
            "No se pudo evaluar la entrevista (el modelo no respondió). Revisa tu conexión/cuenta e intenta de nuevo.",
        ) from e

    conversation_id = f"inapp-{uuid.uuid4().hex[:12]}"
    item_id = await _upsert_candidate(
        conversation_id, transcript, scorecard, project_slug=body.project_slug
    )
    scores = scorecard.get("scores") or {}
    return {
        "ok": True,
        "item_id": item_id,
        "overall": scores.get("overall"),
        "recommendation": scorecard.get("recommendation"),
        "conversation_id": conversation_id,
    }


class InterviewTurnBody(BaseModel):
    project_slug: str | None = None  # de qué búsqueda toma el perfil del cargo
    turns: list[Turn] = []


async def _job_description_for(slug: str | None) -> str:
    if not slug:
        return ""
    from sqlalchemy import select
    from core.db import async_session_factory
    from core.db.models import Project
    async with async_session_factory() as s:
        p = (await s.execute(select(Project).where(Project.slug == slug))).scalar_one_or_none()
        if p is None:
            return ""
        return (getattr(p, "job_description", "") or p.mission or p.description or "").strip()


@router.post("/interview-turn")
async def interview_turn(body: InterviewTurnBody) -> dict:
    """Devuelve la siguiente intervención de Sofía (entrevista in-app por texto).
    No puntúa ni registra: solo conduce la conversación, una pregunta por turno."""
    from core.voice.interview import next_question

    jd = await _job_description_for(body.project_slug)
    turns = [{"role": t.role, "text": t.text} for t in body.turns]
    try:
        message = await next_question(jd, turns)
    except Exception as e:  # noqa: BLE001
        logger.exception("voice: interview-turn falló")
        raise HTTPException(
            502,
            "Sofía no pudo responder (el modelo no contestó). Revisa tu cuenta de Anthropic e intenta de nuevo.",
        ) from e
    return {"message": message}
