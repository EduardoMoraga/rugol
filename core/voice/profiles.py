"""Perfiles de entrevista de Sofía.

Cada perfil adapta el FOCO y las PREGUNTAS GUÍA al tipo de cargo (promotor,
merchandising, ejecutivo comercial, telemarketing…). Sofía sigue evaluando las
competencias del instrumento BARS, pero prioriza las relevantes al perfil y usa
ejemplos de ese rol. El registro es español de CHILE; la voz/acento real se
configura en ElevenLabs (agente). El reclutador elige el perfil en la búsqueda
o al generar la entrevista; 'general' es el por defecto.
"""
from __future__ import annotations

# id → {label, focus, questions}
PROFILES: dict[str, dict] = {
    "general": {
        "label": "General",
        "focus": (
            "Competencias transversales: comunicación, autonomía, cumplimiento, "
            "criterio frente a normas, manejo de presión y honestidad."
        ),
        "questions": [
            "Cuéntame de un logro reciente del que estés orgulloso/a y cómo lo conseguiste.",
            "Describe una vez que tuviste que resolver un problema sin supervisión.",
            "¿Cómo manejas una situación de mucha presión o varios temas a la vez?",
            "Cuéntame de un error que cometiste y qué aprendiste.",
        ],
    },
    "promotor": {
        "label": "Promotor/a de retail",
        "focus": (
            "Orientación al cliente y comunicación cara a cara, ejecución en punto "
            "de venta con supervisión remota, manejo de objeciones, autonomía en "
            "terreno, presentación y proactividad para activar ventas."
        ),
        "questions": [
            "Cuéntame de un día típico tuyo en una sala o punto de venta: ¿qué hacías y cómo te organizabas?",
            "Dame un ejemplo de un cliente difícil o una objeción que enfrentaste y cómo la manejaste.",
            "¿Alguna vez lograste subir las ventas de un producto en tu punto? ¿Qué hiciste exactamente?",
            "Cuando el supervisor no está en la sala, ¿cómo decides qué priorizar?",
            "Cuéntame de una vez que tuviste que montar una exhibición o activación con poco tiempo.",
        ],
    },
    "merchandising": {
        "label": "Merchandising / Reposición",
        "focus": (
            "Ejecución de planogramas y exhibiciones, atención al detalle, "
            "reposición y orden de góndola, relación con el personal de sala, "
            "rigurosidad y cumplimiento de estándares."
        ),
        "questions": [
            "Cuéntame cómo trabajas un planograma: ¿cómo te aseguras de que quede como corresponde?",
            "Dame un ejemplo de una exhibición que armaste y de qué estuviste pendiente para que se viera bien.",
            "¿Qué haces cuando llegas a una sala y la góndola está desordenada o sin stock?",
            "Cuéntame de una vez que detectaste un detalle que otros pasaron por alto.",
            "¿Cómo coordinas con el personal de la tienda para hacer tu trabajo sin fricciones?",
        ],
    },
    "ejecutivo_comercial": {
        "label": "Ejecutivo/a comercial",
        "focus": (
            "Prospección y apertura, manejo de cartera, negociación y cierre, "
            "orientación a metas, seguimiento y relación de largo plazo con el cliente."
        ),
        "questions": [
            "Cuéntame de tu cartera o tu meta más reciente: ¿qué tenías que lograr y cómo te fue?",
            "Dame un ejemplo de una negociación complicada y cómo llegaste al cierre.",
            "¿Cómo prospectas o buscas nuevos clientes? Cuéntame un caso concreto.",
            "Cuéntame de un cliente que estabas por perder y qué hiciste para retenerlo.",
            "¿Cómo organizas tu semana para no descuidar el seguimiento de tus oportunidades?",
        ],
    },
    "telemarketing": {
        "label": "Telemarketing / Call center",
        "focus": (
            "Comunicación telefónica clara, manejo del guion con flexibilidad, "
            "resiliencia ante el rechazo, cumplimiento de metas y calidad, escucha "
            "y manejo de objeciones por teléfono."
        ),
        "questions": [
            "Cuéntame cómo es tu forma de abrir una llamada para enganchar a la persona.",
            "Dame un ejemplo de una llamada en la que te dijeron que no y cómo reaccionaste.",
            "¿Cómo manejas un día con muchas llamadas y rechazos seguidos?",
            "Cuéntame de una vez que cumpliste o superaste tu meta: ¿qué hiciste distinto?",
            "¿Cómo equilibras seguir el guion con adaptarte a lo que dice el cliente?",
        ],
    },
}

_DEFAULT = "general"


def get_profile(pid: str | None) -> dict:
    return PROFILES.get((pid or "").strip().lower()) or PROFILES[_DEFAULT]


def profile_id(pid: str | None) -> str:
    return (pid or "").strip().lower() if (pid or "").strip().lower() in PROFILES else _DEFAULT


def list_profiles() -> list[dict]:
    return [{"id": k, "label": v["label"]} for k, v in PROFILES.items()]
