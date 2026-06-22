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
    token: str | None = None         # si viene de un link ex-ante, lo marcamos usado


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
    # Si vino de un link ex-ante, marcamos la sesión como usada.
    if body.token:
        try:
            from sqlalchemy import select
            from core.db import async_session_factory
            from core.db.models import InterviewLink
            async with async_session_factory() as s:
                link = (await s.execute(select(InterviewLink).where(InterviewLink.token == body.token))).scalar_one_or_none()
                if link is not None:
                    link.used = True
                    await s.commit()
        except Exception:
            logger.exception("voice: no pude marcar el link de entrevista como usado")
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
    profile: str | None = None       # perfil de entrevista (promotor, etc.)


async def _project_jd_profile(slug: str | None) -> tuple[str, str | None]:
    """Devuelve (job_description, interview_profile) de la búsqueda."""
    if not slug:
        return "", None
    from sqlalchemy import select
    from core.db import async_session_factory
    from core.db.models import Project
    async with async_session_factory() as s:
        p = (await s.execute(select(Project).where(Project.slug == slug))).scalar_one_or_none()
        if p is None:
            return "", None
        jd = (getattr(p, "job_description", "") or p.mission or p.description or "").strip()
        return jd, getattr(p, "interview_profile", None)


async def _job_description_for(slug: str | None) -> str:
    jd, _ = await _project_jd_profile(slug)
    return jd


@router.get("/profiles")
async def voice_profiles() -> dict:
    from core.voice.profiles import list_profiles
    return {"profiles": list_profiles()}


@router.post("/interview-turn")
async def interview_turn(body: InterviewTurnBody) -> dict:
    """Devuelve la siguiente intervención de Sofía (entrevista in-app por texto).
    No puntúa ni registra: solo conduce la conversación, una pregunta por turno."""
    from core.voice.interview import next_question

    jd, proj_profile = await _project_jd_profile(body.project_slug)
    profile = body.profile or proj_profile  # explícito > el de la búsqueda
    turns = [{"role": t.role, "text": t.text} for t in body.turns]
    try:
        message = await next_question(jd, turns, profile)
    except Exception as e:  # noqa: BLE001
        logger.exception("voice: interview-turn falló")
        raise HTTPException(
            502,
            "Sofía no pudo responder (el modelo no contestó). Revisa tu cuenta de Anthropic e intenta de nuevo.",
        ) from e
    return {"message": message}


# ---- Entrevista EX-ANTE: link que toma el CANDIDATO ----

class InterviewLinkBody(BaseModel):
    project_slug: str | None = None
    candidate_name: str | None = None
    profile: str | None = None


@router.post("/interview-link")
async def create_interview_link(body: InterviewLinkBody) -> dict:
    """El reclutador genera un link de entrevista para una búsqueda. El candidato
    abre /interview/<token>, conversa con Sofía y al cerrar entra al pipeline."""
    import uuid as _uuid
    from core.db import async_session_factory
    from core.db.models import InterviewLink
    from core.voice.profiles import profile_id

    _, proj_profile = await _project_jd_profile(body.project_slug)
    profile = profile_id(body.profile or proj_profile)
    token = _uuid.uuid4().hex[:16]
    async with async_session_factory() as s:
        link = InterviewLink(
            token=token,
            project_slug=body.project_slug,
            candidate_name=(body.candidate_name or "").strip() or None,
            profile=profile,
        )
        s.add(link)
        await s.commit()
    return {
        "token": token,
        "path": f"/interview/{token}",
        "project_slug": body.project_slug,
        "candidate_name": body.candidate_name,
        "profile": profile,
    }


@router.get("/interview-link/{token}")
async def get_interview_link(token: str) -> dict:
    """Datos públicos de una sesión de entrevista (para la página del candidato)."""
    from sqlalchemy import select
    from core.db import async_session_factory
    from core.db.models import InterviewLink

    async with async_session_factory() as s:
        link = (await s.execute(select(InterviewLink).where(InterviewLink.token == token))).scalar_one_or_none()
        if link is None:
            raise HTTPException(404, "Link de entrevista no encontrado o expirado.")
        jd, proj_profile = await _project_jd_profile(link.project_slug)
        return {
            "found": True,
            "project_slug": link.project_slug,
            "candidate_name": link.candidate_name,
            "profile": getattr(link, "profile", None) or proj_profile or "general",
            "job_description": jd,
            "used": link.used,
        }
