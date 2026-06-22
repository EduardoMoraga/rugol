"""Sincroniza entrevistas de voz de ElevenLabs hacia el pipeline de candidatos.

sync_interviews():
  1. Lista las conversaciones del agente "Sofía".
  2. Por cada una con status=done que NO esté ya en el pipeline
     (rastreada por data.conversation_id en PipelineItem kind=candidate),
     baja el transcript, lo puntúa con BARS y hace UPSERT de un PipelineItem.
  3. Devuelve {processed, created, skipped, errors}.

Autogestionado: idempotente por conversation_id, no duplica candidatos, y se
puede llamar desde el API (POST /api/voice/sync) o desde un job del scheduler.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select

from core.config import get_settings
from core.db import async_session_factory
from core.db.models import PipelineItem
from core.voice import elevenlabs
from core.voice.voice_scorer import score_transcript

logger = logging.getLogger(__name__)

# recommendation del scorecard → etapa del pipeline de candidatos.
# Stages válidas (core/api/pipeline.py): Postulado, Screening, Entrevista,
# Terna, Oferta, Contratado.
_STAGE_BY_RECO: dict[str, str] = {
    "RECOMENDADO": "Terna",
    "CONSIDERAR": "Entrevista",
    "REVISAR_HUMANO": "Entrevista",
    "NO_RECOMENDADO": "Entrevista",
}
_DEFAULT_STAGE = "Screening"


def _overall_to_score(overall: int | float | None) -> int | None:
    """Mapea overall 0-100 a la escala 1-5 del pipeline.

    0-20→1, 21-40→2, 41-60→3, 61-80→4, 81-100→5. None se mantiene None.
    """
    if overall is None:
        return None
    try:
        o = max(0, min(100, int(round(float(overall)))))
    except (TypeError, ValueError):
        return None
    if o <= 20:
        return 1
    if o <= 40:
        return 2
    if o <= 60:
        return 3
    if o <= 80:
        return 4
    return 5


def _build_interview_data(scorecard: dict) -> dict:
    """Extrae el bloque `interview` compacto que queda en data del pipeline."""
    scores = scorecard.get("scores") or {}
    competencies = [
        {
            "name": c.get("competencia") or c.get("competencia_id"),
            "score": c.get("score_bars"),
            "evidence": c.get("evidencia") or [],
            "no_observada": c.get("no_observada", False),
        }
        for c in (scores.get("por_competencia") or [])
    ]
    overall = scores.get("overall")
    reco = scorecard.get("recommendation")
    return {
        "competencies": competencies,
        "verdict": scorecard.get("recommendation_summary") or "",
        "confidence": reco,
        "overall": overall,
        "recommendation": reco,
        "red_flags": scorecard.get("red_flags") or [],
        "strengths": scorecard.get("strengths") or [],
        "weaknesses": scorecard.get("weaknesses") or [],
    }


def _build_note(scorecard: dict, transcript: dict) -> str:
    scores = scorecard.get("scores") or {}
    overall = scores.get("overall")
    reco = scorecard.get("recommendation") or "?"
    summary = scorecard.get("recommendation_summary") or ""
    dur = transcript.get("duration_min")
    dur_txt = f" · {dur} min" if dur else ""
    return f"Entrevista de voz evaluada (BARS): {overall}/100 — {reco}{dur_txt}. {summary}".strip()


async def _existing_conversation_ids(session) -> set[str]:
    """conversation_id ya presentes en el pipeline de candidatos."""
    rows = (
        await session.execute(
            select(PipelineItem).where(PipelineItem.kind == "candidate")
        )
    ).scalars().all()
    ids: set[str] = set()
    for it in rows:
        cid = (it.data or {}).get("conversation_id")
        if cid:
            ids.add(cid)
    return ids


async def sync_interviews(limit: int | None = None) -> dict:
    """Trae entrevistas REALES de ElevenLabs, las puntúa y las deja en el pipeline.

    `limit`: si se da, procesa como máximo esa cantidad de conversaciones nuevas
    (útil para acotar el costo/tiempo del scoring en pruebas).

    Devuelve {processed, created, skipped, errors, details}.
    """
    from core import runtime_state
    api_key, agent_id = runtime_state.elevenlabs_creds()
    if not api_key or not agent_id:
        return {
            "processed": 0, "created": 0, "skipped": 0,
            "errors": ["ELEVENLABS_API_KEY/ELEVENLABS_AGENT_ID no configurados"],
            "details": [],
        }

    try:
        conversations = elevenlabs.list_conversations(api_key, agent_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("voice sync: no se pudo listar conversaciones")
        return {
            "processed": 0, "created": 0, "skipped": 0,
            "errors": [f"list_conversations falló: {e}"], "details": [],
        }

    done = [c for c in conversations if c.get("status") == "done"]

    created = 0
    processed = 0
    errors: list[str] = []
    details: list[dict] = []

    # Snapshot de los que ya están, para no reprocesar.
    async with async_session_factory() as s:
        already = await _existing_conversation_ids(s)

    new_done = [c for c in done if c.get("conversation_id") not in already]
    # Procesamos primero las más antiguas (orden natural de llegada).
    new_done.sort(key=lambda c: c.get("start_time_unix_secs") or 0)
    to_process = new_done[:limit] if limit is not None else new_done

    # Skipped = entrevistas done que ya estaban en el pipeline + las nuevas
    # que el `limit` dejó fuera de esta corrida. Las descartadas por
    # "sin_turnos" se suman más abajo.
    skipped = (len(done) - len(new_done)) + (len(new_done) - len(to_process))

    for c in to_process:
        cid = c.get("conversation_id")
        if not cid:
            continue
        try:
            transcript = elevenlabs.get_transcript(api_key, cid)
            if not transcript.get("turns"):
                skipped += 1
                details.append({"conversation_id": cid, "status": "sin_turnos"})
                continue

            scorecard = await score_transcript(transcript)
            await _upsert_candidate(cid, transcript, scorecard)
            created += 1
            processed += 1
            scores = scorecard.get("scores") or {}
            details.append({
                "conversation_id": cid,
                "status": "created",
                "title": transcript.get("candidate", {}).get("name"),
                "overall": scores.get("overall"),
                "recommendation": scorecard.get("recommendation"),
            })
        except Exception as e:  # noqa: BLE001 — un fallo no frena el resto
            logger.exception("voice sync: error procesando %s", cid)
            errors.append(f"{cid}: {e}")
            details.append({"conversation_id": cid, "status": "error", "error": str(e)})

    return {
        "processed": processed,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }


async def _upsert_candidate(
    conversation_id: str,
    transcript: dict,
    scorecard: dict,
    project_slug: str | None = None,
) -> int:
    """Crea (o actualiza) el PipelineItem candidato de esta entrevista.

    Si `project_slug` se entrega, liga el candidato a esa búsqueda. Devuelve el
    id del PipelineItem creado o actualizado. Reusado por la sync de ElevenLabs
    y por la entrevista in-app (POST /api/voice/score-text)."""
    cand = transcript.get("candidate") or {}
    scores = scorecard.get("scores") or {}
    overall = scores.get("overall")
    reco = scorecard.get("recommendation") or "REVISAR_HUMANO"
    stage = _STAGE_BY_RECO.get(reco, _DEFAULT_STAGE)
    score = _overall_to_score(overall)
    name = cand.get("name") or "Candidato sin nombre"
    position = cand.get("position") or None

    data = {
        "conversation_id": conversation_id,
        "candidate_email": cand.get("email") or "",
        "candidate_phone": cand.get("phone") or "",
        "interview_date": transcript.get("date") or "",
        "duration_min": transcript.get("duration_min"),
        "interview": _build_interview_data(scorecard),
        "scorecard": scorecard,
    }
    note_text = _build_note(scorecard, transcript)
    now = dt.datetime.now(dt.UTC).isoformat()

    async with async_session_factory() as s:
        # Buscar por conversation_id (idempotencia). No hay índice JSON portable
        # entre SQLite/PG, así que filtramos en Python sobre los candidatos.
        rows = (
            await s.execute(
                select(PipelineItem).where(PipelineItem.kind == "candidate")
            )
        ).scalars().all()
        existing = next(
            (it for it in rows if (it.data or {}).get("conversation_id") == conversation_id),
            None,
        )

        if existing is None:
            it = PipelineItem(
                kind="candidate",
                title=name[:200],
                subtitle=position,
                stage=stage,
                score=score,
                source_agent="hro-sofia",
                project_slug=project_slug,
                notes=[{"at": now, "agent": "hro-sofia", "text": note_text}],
                data=data,
            )
            s.add(it)
            await s.commit()
            await s.refresh(it)
            return it.id
        else:
            existing.title = name[:200]
            existing.subtitle = position
            existing.stage = stage
            existing.score = score
            existing.source_agent = "hro-sofia"
            if project_slug:
                existing.project_slug = project_slug
            existing.data = {**(existing.data or {}), **data}
            notes = list(existing.notes or [])
            notes.append({"at": now, "agent": "hro-sofia", "text": note_text})
            existing.notes = notes
            await s.commit()
            return existing.id
