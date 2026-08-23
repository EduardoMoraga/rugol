"""Scorer BARS headless para entrevistas de voz.

Adaptado de HRO2/voice-interviewer/scorer/hr_voice_scorer.py para correr dentro
de Rugol. Dado un transcript devuelve el scorecard dict (6 competencias BARS 1-5
con evidencia citada, overall 0-100, recommendation, red_flags).

Para puntuar usa el MISMO patrón que el resto de Rugol: claude-agent-sdk con
`setting_sources=["user"]` (suscripción Claude Pro/Max autenticada en la máquina,
sin token ni API key). Si la SDK falla, cae al CLI `claude -p`. Si hay
ANTHROPIC_API_KEY válida, se usa la API directa (más rápida) como primer intento.

Reglas de compliance (heredadas del instrumento): se evalúa SOLO contenido
verbal; cada puntaje cita evidencia textual del candidato; el output es una
recomendación para revisión humana, nunca una decisión automática.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

from core import llm_models

logger = logging.getLogger(__name__)

INSTRUMENTO_PATH = Path(__file__).resolve().parent / "instrumento_v1.json"

# JSON Schema del scorecard (mismo contrato que HROv2). Se incrusta en el
# prompt para guiar la salida del modelo en los caminos que no soportan
# structured output nativo.
SCHEMA = {
    "type": "object",
    "properties": {
        "candidate": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "position_applied": {"type": "string"},
            },
            "required": ["name", "position_applied"],
            "additionalProperties": False,
        },
        "scores": {
            "type": "object",
            "properties": {
                "overall": {"type": "integer"},
                "por_competencia": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "competencia_id": {"type": "string"},
                            "competencia": {"type": "string"},
                            "score_bars": {"type": ["integer", "null"]},
                            "no_observada": {"type": "boolean"},
                            "justificacion": {"type": "string"},
                            "evidencia": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Citas textuales del candidato que sustentan el puntaje",
                            },
                        },
                        "required": [
                            "competencia_id", "competencia", "score_bars",
                            "no_observada", "justificacion", "evidencia",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["overall", "por_competencia"],
            "additionalProperties": False,
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "red_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "descripcion": {"type": "string"},
                    "evidencia": {"type": "string"},
                },
                "required": ["descripcion", "evidencia"],
                "additionalProperties": False,
            },
        },
        "recommendation": {
            "type": "string",
            "enum": ["RECOMENDADO", "CONSIDERAR", "REVISAR_HUMANO", "NO_RECOMENDADO"],
        },
        "recommendation_summary": {"type": "string"},
        "preguntas_sugeridas_entrevista_humana": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "candidate", "scores", "strengths", "weaknesses", "red_flags",
        "recommendation", "recommendation_summary",
        "preguntas_sugeridas_entrevista_humana",
    ],
    "additionalProperties": False,
}

SYSTEM = """Sos el evaluador psicométrico del módulo de reclutamiento de Rugol. Puntuás transcripciones de entrevistas estructuradas de voz contra un instrumento BARS, con rigor metodológico.

REGLAS INVIOLABLES:
1. Evaluás SOLO el contenido verbal: qué dijo el candidato. Prohibido inferir desde pausas, muletillas, dudas, fluidez, acento o estilo de habla. Un candidato que duda pero da un ejemplo concreto puntúa por el ejemplo.
2. Cada puntaje DEBE citar textualmente la(s) frase(s) del candidato que lo justifican (campo evidencia). Si no hay evidencia suficiente para una competencia, score_bars=null y no_observada=true — no penalices con nota baja lo que no se observó.
3. Aplicá las anclas BARS literalmente: el puntaje es el nivel cuya descripción mejor coincide con la conducta RELATADA, no una impresión general.
4. red_flags: solo conductas verbalizadas concretas según las reglas del instrumento. El nerviosismo NUNCA es red flag.
5. overall = promedio ponderado (pesos del instrumento) de las competencias observadas, reescalado a 0-100 (score_bars 1->20, 5->100). Las no observadas se excluyen del promedio y renormalizan los pesos.
6. recommendation según umbral_recomendacion del instrumento. Recordá: tu output es insumo para un reclutador humano; ante la duda, REVISAR_HUMANO.
7. Escribe justificaciones y resúmenes en español neutro, profesional y conciso.

El transcript te llega con turnos {role, text}: role="agent" es la entrevistadora (Sofía), role="user" es el candidato. Evaluá únicamente los turnos del candidato (user)."""


def _load_instrumento() -> dict:
    return json.loads(INSTRUMENTO_PATH.read_text(encoding="utf-8"))


def _build_user_msg(transcript: dict, instrumento: dict) -> str:
    return (
        "INSTRUMENTO (rúbricas BARS, pesos, reglas y umbrales):\n"
        + json.dumps(instrumento, ensure_ascii=False)
        + "\n\nTRANSCRIPCIÓN DE LA ENTREVISTA A EVALUAR:\n"
        + json.dumps(transcript, ensure_ascii=False)
        + "\n\nGenerá el scorecard completo."
    )


def _extract_json(text: str) -> dict:
    """Extrae el primer objeto JSON de un texto (tolera fences de markdown)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Sin JSON en la respuesta del modelo: {text[:200]}")
    return json.loads(text[start : end + 1])


# --- Camino 1: API de Anthropic (solo si hay ANTHROPIC_API_KEY válida) -------

def _score_via_api(api_key: str, user_msg: str) -> tuple[dict, str]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=llm_models.OPUS,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    text = next(b.text for b in response.content if getattr(b, "type", None) == "text")
    return json.loads(text), getattr(response, "model", "claude-api")


# --- Camino 2: claude-agent-sdk sobre la suscripción (patrón Rugol) ----------

async def _score_via_sdk(user_msg: str) -> tuple[dict, str]:
    from claude_agent_sdk import ClaudeAgentOptions, query

    prompt = (
        user_msg
        + "\n\nRespondé ÚNICAMENTE con el objeto JSON del scorecard, sin markdown "
        "ni texto adicional, cumpliendo EXACTAMENTE este JSON Schema:\n"
        + json.dumps(SCHEMA, ensure_ascii=False)
    )
    # Subscription mode: limpiamos vars de API key para que el CLI use la
    # sesión Claude Pro/Max autenticada (~/.claude), igual que claude_runner.
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM,
        permission_mode="bypassPermissions",
        setting_sources=["user"],
        # Sin herramientas: es una tarea de puro razonamiento sobre texto.
        tools=[],
        env=env,
        max_turns=1,
    )

    parts: list[str] = []
    model_name = "claude-code-subscription"
    async for message in query(prompt=prompt, options=options):
        kind = type(message).__name__
        if kind == "AssistantMessage":
            for block in getattr(message, "content", []) or []:
                btype = getattr(block, "type", None) or type(block).__name__.lower()
                if btype in {"text", "textblock"}:
                    parts.append(getattr(block, "text", "") or "")
        elif kind == "ResultMessage":
            result = getattr(message, "result", None)
            if result and not parts:
                parts.append(str(result))
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("claude-agent-sdk no devolvió texto")
    return _extract_json(text), model_name


# --- Camino 3: CLI `claude -p` (fallback final) ------------------------------

def _score_via_cli(user_msg: str) -> tuple[dict, str]:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("No hay `claude` CLI instalado para el fallback de scoring")
    prompt = (
        SYSTEM
        + "\n\n" + user_msg
        + "\n\nRespondé ÚNICAMENTE con el objeto JSON del scorecard, sin markdown "
        "ni texto adicional, cumpliendo EXACTAMENTE este JSON Schema:\n"
        + json.dumps(SCHEMA, ensure_ascii=False)
    )
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        [claude_bin, "-p", "--output-format", "json"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI falló ({result.returncode}): {result.stderr[:500]}")
    envelope = json.loads(result.stdout)
    return _extract_json(envelope["result"]), "claude-code-cli"


async def score_transcript(transcript: dict) -> dict:
    """Puntúa un transcript {candidate, turns} y devuelve el scorecard dict.

    Orden de intentos:
      1. API Anthropic si ANTHROPIC_API_KEY está seteada (rápido, structured).
      2. claude-agent-sdk sobre la suscripción (patrón estándar de Rugol).
      3. CLI `claude -p` (fallback de último recurso).
    """
    instrumento = _load_instrumento()
    user_msg = _build_user_msg(transcript, instrumento)

    scorecard: dict | None = None
    modelo: str | None = None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            scorecard, modelo = _score_via_api(api_key, user_msg)
        except Exception as e:  # noqa: BLE001 — key inválida/revocada → seguimos
            logger.warning("voice scorer: API key falló (%s) → suscripción", e)

    if scorecard is None:
        try:
            scorecard, modelo = await _score_via_sdk(user_msg)
        except Exception as e:  # noqa: BLE001 — SDK falló → CLI
            logger.warning("voice scorer: claude-agent-sdk falló (%s) → claude -p CLI", e)

    if scorecard is None:
        scorecard, modelo = _score_via_cli(user_msg)

    scorecard["_meta"] = {
        "instrumento_version": instrumento.get("version"),
        "fecha_evaluacion": date.today().isoformat(),
        "modelo": modelo,
        "disclaimer": (
            "Recomendación generada por IA para revisión humana. "
            "Ninguna decisión de descarte es automática."
        ),
    }
    return scorecard


# --- Texto libre reutilizable (entrevista in-app) ----------------------------
# Mismo orden de intentos que el scorer, pero devuelve texto plano en vez de
# JSON. Lo usa core/voice/interview.py para conducir la conversación de Sofía.

async def _text_via_sdk(system: str, user: str) -> str:
    from claude_agent_sdk import ClaudeAgentOptions, query

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    options = ClaudeAgentOptions(
        system_prompt=system,
        permission_mode="bypassPermissions",
        setting_sources=["user"],
        tools=[],
        env=env,
        max_turns=1,
    )
    parts: list[str] = []
    async for message in query(prompt=user, options=options):
        if type(message).__name__ == "AssistantMessage":
            for block in getattr(message, "content", []) or []:
                btype = getattr(block, "type", None) or type(block).__name__.lower()
                if btype in {"text", "textblock"}:
                    parts.append(getattr(block, "text", "") or "")
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("claude-agent-sdk no devolvió texto")
    return text


def _text_via_api(api_key: str, system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=llm_models.SONNET,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return next(b.text for b in response.content if getattr(b, "type", None) == "text").strip()


async def complete_text(system: str, user: str) -> str:
    """Una vuelta de texto libre. Suscripción (SDK) → API key → error claro."""
    try:
        return await _text_via_sdk(system, user)
    except Exception as e:  # noqa: BLE001
        logger.warning("interview: SDK falló (%s) → API key", e)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return _text_via_api(api_key, system, user)
    raise RuntimeError("No hay forma de generar texto: ni suscripción (~/.claude) ni ANTHROPIC_API_KEY.")
