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


# El scorer recomienda con este enum; el dashboard muestra veredicto/confianza
# con sus propios enums. Mapeamos para que la UI no reciba frases crudas (lo que
# rompía el layout y dejaba "interviews.verdict.<frase>" como key-leak).
_VERDICT_BY_RECO: dict[str, str] = {
    "RECOMENDADO": "avanzar",
    "CONSIDERAR": "dudoso",
    "REVISAR_HUMANO": "dudoso",
    "NO_RECOMENDADO": "descartar",
}
_CONFIDENCE_BY_RECO: dict[str, str] = {
    "RECOMENDADO": "alta",
    "NO_RECOMENDADO": "alta",
    "CONSIDERAR": "media",
    "REVISAR_HUMANO": "baja",
}


def _evidence_to_text(ev) -> str:
    """La evidencia del scorer puede venir como lista de citas; la unimos en
    texto legible (antes se renderizaba como array → 'productolos procesadores')."""
    if isinstance(ev, list):
        return "\n".join(str(x).strip() for x in ev if str(x).strip())
    return str(ev or "").strip()


def _build_interview_data(scorecard: dict) -> dict:
    """Extrae el bloque `interview` compacto que queda en data del pipeline."""
    scores = scorecard.get("scores") or {}
    competencies = [
        {
            "name": c.get("competencia") or c.get("competencia_id"),
            "score": c.get("score_bars"),
            "evidence": _evidence_to_text(c.get("evidencia")),
            "no_observada": c.get("no_observada", False),
        }
        for c in (scores.get("por_competencia") or [])
    ]
    overall = scores.get("overall")
    reco = (scorecard.get("recommendation") or "REVISAR_HUMANO").upper()
    return {
        "competencies": competencies,
        "verdict": _VERDICT_BY_RECO.get(reco, "dudoso"),
        "confidence": _CONFIDENCE_BY_RECO.get(reco, "media"),
        "summary": scorecard.get("recommendation_summary") or "",
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


_columns_ensured = False


async def _ensure_pipeline_columns() -> None:
    """Asegura la columna indexada `conversation_id` en pipeline_items (SQLite).

    `create_all` no agrega columnas a tablas existentes, así que migramos en
    caliente (idempotente) y backfilleamos desde el JSON `data` para que las
    entrevistas ya cargadas no se reprocesen. Si algo falla, no rompe la sync:
    el lookup cae al escaneo del JSON."""
    global _columns_ensured
    if _columns_ensured:
        return
    from sqlalchemy import text
    try:
        async with async_session_factory() as s:
            rows = (await s.execute(text("PRAGMA table_info(pipeline_items)"))).all()
            cols = {r[1] for r in rows}
            if cols and "conversation_id" not in cols:
                await s.execute(text("ALTER TABLE pipeline_items ADD COLUMN conversation_id VARCHAR(64)"))
                # Backfill desde data.conversation_id para no reprocesar lo ya cargado.
                await s.execute(text(
                    "UPDATE pipeline_items SET conversation_id = json_extract(data, '$.conversation_id') "
                    "WHERE conversation_id IS NULL AND json_extract(data, '$.conversation_id') IS NOT NULL"
                ))
                await s.commit()
                logger.info("voice sync: columna conversation_id agregada + backfill a pipeline_items")
    except Exception:  # noqa: BLE001
        logger.exception("voice sync: no pude asegurar la columna conversation_id (sigo con scan JSON)")
    _columns_ensured = True


async def _existing_conversation_ids(session) -> set[str]:
    """conversation_id ya presentes en el pipeline de candidatos (O(1) por índice)."""
    await _ensure_pipeline_columns()
    try:
        rows = (
            await session.execute(
                select(PipelineItem.conversation_id).where(
                    PipelineItem.kind == "candidate",
                    PipelineItem.conversation_id.is_not(None),
                )
            )
        ).scalars().all()
        return {c for c in rows if c}
    except Exception:  # noqa: BLE001 — DB vieja sin la columna → fallback al scan
        rows2 = (
            await session.execute(
                select(PipelineItem).where(PipelineItem.kind == "candidate")
            )
        ).scalars().all()
        return {cid for it in rows2 if (cid := (it.data or {}).get("conversation_id"))}


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

    await _ensure_pipeline_columns()
    async with async_session_factory() as s:
        # Idempotencia O(1) por la columna indexada conversation_id; si la DB es
        # vieja y no tiene la columna, cae al escaneo en Python.
        try:
            existing = (
                await s.execute(
                    select(PipelineItem).where(
                        PipelineItem.kind == "candidate",
                        PipelineItem.conversation_id == conversation_id,
                    )
                )
            ).scalar_one_or_none()
        except Exception:  # noqa: BLE001
            rows = (
                await s.execute(select(PipelineItem).where(PipelineItem.kind == "candidate"))
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
                conversation_id=conversation_id,
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
            existing.conversation_id = conversation_id
            if project_slug:
                existing.project_slug = project_slug
            existing.data = {**(existing.data or {}), **data}
            notes = list(existing.notes or [])
            notes.append({"at": now, "agent": "hro-sofia", "text": note_text})
            existing.notes = notes
            await s.commit()
            return existing.id
