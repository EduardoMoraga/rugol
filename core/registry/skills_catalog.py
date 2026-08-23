"""Hacer que las skills de Rugol le lleguen al agente.

El bug que esto arregla: `~/.rugol/skills/*.md` se escaneaba a la base y se
mostraba en el dashboard, pero **nunca llegaba al modelo**. El system prompt
decía "podés invocar skills como siempre", y eso apuntaba al descubrimiento
propio de Claude Code, que mira `~/.claude/skills` — otra carpeta. Las skills
de Rugol eran decoración.

Por qué un catálogo en el prompt y no un symlink a `~/.claude/skills`:

  - No toca la configuración de Claude Code del usuario. Rugol es un
    invitado en esa máquina.
  - **Funciona con los dos motores.** Codex no conoce el formato de skills de
    Claude Code; un bloque de texto con nombre, para qué sirve y dónde está el
    archivo lo entienden los dos.
  - El agente lee la skill sólo cuando la necesita, así que cien skills no
    cuestan cien veces más contexto.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Tope de skills listadas. Con más que esto el bloque empieza a competir con
# el trabajo real por el contexto; si alguien llega acá, conviene que las
# skills vivan por proyecto y no todas juntas.
MAX_LISTED = 40


def render_catalogue(skills: list[tuple[str, str, str]]) -> str | None:
    """(nombre, descripción, ruta) → el bloque que va al system prompt."""
    if not skills:
        return None

    listed = skills[:MAX_LISTED]
    lines = [
        "## Skills disponibles en esta instalación de Rugol",
        "",
        "Son procedimientos escritos que podés seguir. NO están cargados en tu",
        "contexto: cada uno es un archivo. Cuando una tarea coincida con la",
        "descripción de abajo, leé el archivo con Read y seguí sus pasos.",
        "Si ninguna aplica, trabajá normalmente — no fuerces una.",
        "",
    ]
    for name, description, path in listed:
        desc = (description or "").strip().replace("\n", " ")
        if len(desc) > 180:
            desc = desc[:177].rstrip() + "…"
        lines.append(f"- **{name}** — {desc or 'sin descripción'}")
        lines.append(f"  `{path}`")
    if len(skills) > MAX_LISTED:
        lines.append("")
        lines.append(
            f"(y {len(skills) - MAX_LISTED} más — listalas con "
            "`GET /api/skills` si necesitás una que no esté arriba)"
        )
    return "\n".join(lines)


async def load_catalogue() -> str | None:
    """Lee las skills registradas y devuelve el bloque, o None si no hay.

    Nunca levanta: quedarse sin catálogo degrada al comportamiento anterior,
    que es correcto aunque más pobre.
    """
    try:
        from sqlalchemy import select

        from core.db import async_session_factory
        from core.db.models import Skill

        async with async_session_factory() as session:
            rows = (await session.execute(
                select(Skill.name, Skill.description, Skill.source_path).order_by(Skill.name)
            )).all()
        return render_catalogue([(r[0], r[1], r[2]) for r in rows])
    except Exception:
        logger.exception("no pude armar el catálogo de skills — el agente corre sin él")
        return None
