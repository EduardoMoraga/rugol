"""Soul — World State block.

Claude has no clock. Without an injected "current date/time" string the
agent will either hallucinate the day of the week or assume training-cutoff
dates. This module renders a small block prepended to every system prompt
so the model always knows the real now in the user's timezone.

Inspired by the 2026-05-11 incident where Gugol told Eduardo "today is
Sunday" on a Monday because no date context was being passed.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.config import get_settings

logger = logging.getLogger(__name__)


_SPANISH_WEEKDAYS = (
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
)
_SPANISH_MONTHS = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _resolve_zone() -> ZoneInfo:
    tz_name = (get_settings().SCHEDULER_TIMEZONE or "UTC").strip()
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("unknown timezone %r, falling back to UTC", tz_name)
        return ZoneInfo("UTC")


def _format_offset(offset_seconds: int) -> str:
    sign = "-" if offset_seconds < 0 else "+"
    abs_minutes = abs(offset_seconds) // 60
    hours, minutes = divmod(abs_minutes, 60)
    if minutes:
        return f"{sign}{hours}:{minutes:02d}"
    return f"{sign}{hours}"


def build_world_state_block(
    *,
    run_id: int | None = None,
    source: str | None = None,
    agent_name: str | None = None,
    schedule_id: int | None = None,
) -> str:
    """Render the World State block prepended to every run's system prompt.

    Includes:
    - Real current datetime in the configured timezone, in Spanish.
    - Day-of-week label and whether it's a weekday.
    - UTC offset (so the model can convert if asked).
    - Source of the current run (schedule | telegram | slack | dashboard | api).
    """
    zone = _resolve_zone()
    now = datetime.now(zone)
    weekday_idx = now.weekday()  # 0 = Monday
    weekday = _SPANISH_WEEKDAYS[weekday_idx]
    is_weekday = weekday_idx < 5
    month = _SPANISH_MONTHS[now.month]

    utc_offset_seconds = int(now.utcoffset().total_seconds()) if now.utcoffset() else 0
    offset_str = _format_offset(utc_offset_seconds)
    tz_label = zone.key or "UTC"

    lines: list[str] = [
        "## Contexto del run (estado del mundo)",
        f"- **Ahora**: {weekday} {now.day} de {month} de {now.year}, {now.strftime('%H:%M')} ({tz_label}, UTC{offset_str}).",
        f"- **Día**: {'laborable' if is_weekday else 'fin de semana'}.",
        f"- **ISO timestamp**: `{now.isoformat()}`.",
    ]

    if source or agent_name or run_id is not None or schedule_id is not None:
        meta_bits: list[str] = []
        if agent_name:
            meta_bits.append(f"agente=`{agent_name}`")
        if run_id is not None:
            meta_bits.append(f"run_id=`{run_id}`")
        if source:
            meta_bits.append(f"source=`{source}`")
        if schedule_id is not None:
            meta_bits.append(f"schedule_id=`{schedule_id}`")
        lines.append(f"- **Run**: {' · '.join(meta_bits)}.")

    lines.append("")
    lines.append(
        "Esta fecha y hora son **reales** — no son tu conocimiento de entrenamiento. "
        "Si necesitas razonar sobre cuándo ocurre algo (hoy, mañana, esta semana), "
        "usa esta marca de tiempo como verdad absoluta. NUNCA digas 'hoy es X' "
        "basándote en suposición — usa el dato de arriba."
    )
    return "\n".join(lines).strip()
