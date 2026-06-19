"""Cliente HTTP de ElevenLabs Conversational AI.

Solo lectura: lista las conversaciones del agente de voz "Sofía" y baja el
detalle (transcript + datos del candidato). No envía nada a ElevenLabs.

Autenticación: header `xi-api-key`. Endpoints (base https://api.elevenlabs.io):
  GET /v1/convai/conversations?agent_id=<id>&page_size=30   → lista
  GET /v1/convai/conversations/{conversation_id}            → detalle

El detalle trae:
  - transcript: [{role: "agent"|"user", message: str, ...}]
  - metadata: {call_duration_secs, start_time_unix_secs, ...}
  - los datos del formulario web viajan como dynamic_variables dentro de
    conversation_initiation_client_data (candidate_name/email/phone, position).

get_transcript() normaliza todo al formato que consume el scorer:
  {candidate: {name, email, phone, position}, turns: [{role, text}]}
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.elevenlabs.io"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _headers(api_key: str) -> dict[str, str]:
    return {"xi-api-key": api_key}


def list_conversations(
    api_key: str, agent_id: str, page_size: int = 30
) -> list[dict[str, Any]]:
    """Lista las conversaciones del agente. Devuelve la lista cruda de items.

    Cada item incluye al menos: conversation_id, status (done|failed|...),
    message_count, call_duration_secs, start_time_unix_secs.
    """
    url = f"{BASE_URL}/v1/convai/conversations"
    params = {"agent_id": agent_id, "page_size": page_size}
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(url, headers=_headers(api_key), params=params)
        resp.raise_for_status()
        data = resp.json()
    return data.get("conversations", []) or []


def get_conversation_detail(api_key: str, conversation_id: str) -> dict[str, Any]:
    """Baja el detalle crudo de una conversación (transcript + metadata)."""
    url = f"{BASE_URL}/v1/convai/conversations/{conversation_id}"
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(url, headers=_headers(api_key))
        resp.raise_for_status()
        return resp.json()


def _extract_candidate(detail: dict[str, Any]) -> dict[str, str]:
    """Lee los datos del candidato desde dynamic_variables del formulario web.

    Tolera que ElevenLabs ubique las variables en distintos lugares según la
    versión del payload (conversation_initiation_client_data o metadata).
    """
    init = detail.get("conversation_initiation_client_data") or {}
    dyn = init.get("dynamic_variables") or {}
    if not dyn:
        # Fallback: algunas respuestas ponen el análisis/variables en metadata.
        meta = detail.get("metadata") or {}
        dyn = (meta.get("conversation_initiation_client_data") or {}).get(
            "dynamic_variables"
        ) or meta.get("dynamic_variables") or {}

    cid = detail.get("conversation_id") or ""
    name = (dyn.get("candidate_name") or "").strip()
    if not name:
        name = f"Candidato ({cid[-8:]})" if cid else "Candidato sin nombre"
    return {
        "name": name,
        "email": (dyn.get("candidate_email") or "").strip(),
        "phone": (dyn.get("candidate_phone") or "").strip(),
        "position": (dyn.get("position") or "Promotor/a - Merchandiser").strip(),
    }


def _extract_turns(detail: dict[str, Any]) -> list[dict[str, str]]:
    """Convierte el transcript de ElevenLabs a [{role, text}] sin turnos vacíos."""
    turns: list[dict[str, str]] = []
    for t in detail.get("transcript") or []:
        role = t.get("role")
        text = (t.get("message") or "").strip()
        if not text:
            continue
        # Normalizamos a los roles que espera el scorer: agent | user.
        norm_role = "agent" if role == "agent" else "user"
        turns.append({"role": norm_role, "text": text})
    return turns


def get_transcript(api_key: str, conversation_id: str) -> dict[str, Any]:
    """Baja una conversación y la devuelve en el formato que espera el scorer.

    Estructura:
      {
        "conversation_id": str,
        "date": "YYYY-MM-DD HH:MM",
        "duration_min": float,
        "candidate": {"name", "email", "phone", "position"},
        "turns": [{"role": "agent"|"user", "text": str}, ...],
      }
    """
    detail = get_conversation_detail(api_key, conversation_id)
    meta = detail.get("metadata") or {}
    dur_secs = meta.get("call_duration_secs") or 0
    start_unix = meta.get("start_time_unix_secs")
    try:
        date_str = (
            datetime.fromtimestamp(start_unix).strftime("%Y-%m-%d %H:%M")
            if start_unix
            else ""
        )
    except (TypeError, ValueError, OSError):
        date_str = ""

    return {
        "conversation_id": detail.get("conversation_id") or conversation_id,
        "date": date_str,
        "duration_min": round(dur_secs / 60, 1) if dur_secs else 0.0,
        "candidate": _extract_candidate(detail),
        "turns": _extract_turns(detail),
    }
