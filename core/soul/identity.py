"""Identity block — first thing the agent reads on every run.

The identity is built from immutable agent fields (name, description) plus
a lightweight relationship summary derived from the memory index. Reflection
never writes to identity directly; it writes to memory, which then surfaces
back through the relationship line. This keeps the agent recognisably
itself even as it learns.
"""
from __future__ import annotations

from core.memory import list_memories


def _short_description(description: str, max_chars: int = 280) -> str:
    """Trim description to a single readable paragraph."""
    text = (description or "").strip().replace("\n\n", " ").replace("\n", " ")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def build_identity_block(
    agent_name: str,
    description: str,
    run_count: int = 0,
    last_run_at_iso: str | None = None,
) -> str:
    """Render the identity block prepended to the system prompt.

    Why these fields:
    - name + description: the agent's deliberate self, set by whoever
      wrote the .md template. Stable across runs.
    - run_count + last_run_at: a frame of "you have been here before",
      which is what triggers memory-aware behaviour in the model.
    - memory count: signals depth of relationship without dumping the
      whole memory inside identity (the memory block does that).
    """
    desc = _short_description(description) or "(no description — operate from your training and memory)"

    try:
        mems = list_memories(agent_name)
        mem_count = len(mems)
    except Exception:
        mem_count = 0

    lines = [
        "## Tu identidad",
        f"Eres **{agent_name}**.",
        "",
        f"**Quién eres (definición estable):** {desc}",
        "",
    ]

    if run_count > 0 or mem_count > 0:
        relationship_bits: list[str] = []
        if run_count > 0:
            relationship_bits.append(f"Llevas {run_count} run(s) ejecutado(s)")
        if last_run_at_iso:
            relationship_bits.append(f"último: {last_run_at_iso}")
        if mem_count > 0:
            relationship_bits.append(f"{mem_count} memoria(s) acumulada(s)")
        lines.append("**Historial:** " + " · ".join(relationship_bits) + ".")
        lines.append("")

    lines.append(
        "Habla y actúa como tú mismo. La memoria persistente abajo es lo que "
        "ya has aprendido — úsala antes de pedir información que ya deberías saber."
    )
    return "\n".join(lines).strip()
