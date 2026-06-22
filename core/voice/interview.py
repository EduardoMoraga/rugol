"""Entrevista in-app de Sofía (texto).

Conduce la conversación turno a turno: Sofía hace UNA pregunta por intervención,
método STAR, cubriendo las 6 competencias del instrumento BARS. NO puntúa ni
registra nada — eso lo hace el scorer al cerrar (POST /api/voice/score-text).

Reusa `complete_text` (suscripción → API) de voice_scorer y las competencias de
`instrumento_v1.json`, así la entrevista y la evaluación hablan del mismo marco.
"""
from __future__ import annotations

import logging

from core.voice.voice_scorer import _load_instrumento, complete_text

logger = logging.getLogger(__name__)


def _competency_names() -> list[str]:
    try:
        inst = _load_instrumento()
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for c in inst.get("competencias", []) or []:
        name = c.get("nombre") or c.get("competencia") or c.get("id")
        if name:
            out.append(str(name))
    return out


def _system_prompt(job_description: str) -> str:
    comps = _competency_names()
    comp_block = (
        "Competencias a explorar (usa el método STAR para sacar ejemplos reales):\n- "
        + "\n- ".join(comps)
        if comps
        else "Explora competencias conductuales con ejemplos reales (método STAR)."
    )
    jd = (job_description or "").strip()
    jd_block = f"\n\nPerfil del cargo para esta búsqueda:\n{jd}" if jd else ""
    return (
        "Eres Sofía, entrevistadora del equipo de selección. Conduces una entrevista "
        "estructurada por competencias: cálida, profesional y rigurosa. Hablas en "
        "español neutro latino (NO uses voseo argentino: di 'tú', 'cuéntame', 'dame un ejemplo').\n\n"
        "Reglas de la entrevista:\n"
        "- Haz UNA sola pregunta por intervención. Nada de listas de preguntas.\n"
        "- Busca ejemplos concretos y reales (Situación, Tarea, Acción, Resultado).\n"
        "- No evalúas en voz alta, no opinas sobre las respuestas, no adelantas resultados "
        "ni das puntajes. Solo escuchas y repreguntas para profundizar.\n"
        "- NUNCA preguntes por estado civil, hijos, edad, religión, salud u origen.\n"
        "- Si la respuesta fue vaga, repregunta pidiendo el ejemplo concreto antes de avanzar.\n"
        "- Mantén tus intervenciones breves (1-3 oraciones).\n\n"
        + comp_block
        + jd_block
        + "\n\nDevuelve ÚNICAMENTE tu siguiente intervención como Sofía (texto plano, "
        "sin prefijos como 'Sofía:'). Si todavía no empezó la entrevista, preséntate en una "
        "línea y haz la primera pregunta."
    )


def _format_turns(turns: list[dict], max_turns: int = 40) -> str:
    recent = turns[-max_turns:]
    lines = []
    for t in recent:
        role = (t.get("role") or "").lower()
        who = "Sofía" if role.startswith("sof") else "Candidato"
        text = (t.get("text") or "").strip()
        if text:
            lines.append(f"{who}: {text}")
    return "\n".join(lines)


async def next_question(job_description: str, turns: list[dict]) -> str:
    """Devuelve la siguiente intervención de Sofía dada la conversación hasta ahora."""
    system = _system_prompt(job_description)
    convo = _format_turns(turns)
    if not convo:
        user = "Empieza la entrevista: preséntate en una línea y haz tu primera pregunta."
    else:
        user = (
            "Conversación hasta ahora:\n"
            + convo
            + "\n\nDa tu siguiente intervención (una sola pregunta, o un cierre breve "
            "y cálido si ya cubriste lo esencial de las competencias)."
        )
    text = await complete_text(system, user)
    # Por si el modelo igual antepone "Sofía:" — lo limpiamos.
    for prefix in ("Sofía:", "Sofia:", "**Sofía:**", "Entrevistadora:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text
