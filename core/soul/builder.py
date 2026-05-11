"""Compose the soul context: identity + auto-memory rules.

The persistent memory block is added separately by the orchestrator
(via core.memory.build_memory_block) so we keep the existing call site
untouched. The soul context wraps everything in a clear section header
so the model knows what it is reading.
"""
from __future__ import annotations

from core.soul.auto_memory import AUTO_MEMORY_RULES
from core.soul.identity import build_identity_block


def build_soul_context(
    agent_name: str,
    description: str,
    run_count: int = 0,
    last_run_at_iso: str | None = None,
) -> str:
    """Return the combined identity + auto-memory block.

    Caller appends the existing memory block (from core.memory) and the
    project context separately. Layout in the final system prompt:

        <SDK preset>
        <SYSTEM_PROMPT_APPEND>
        <build_soul_context>     ← identity + auto-memory rules
        <project_context>        ← optional
        <memory_block>           ← already-known facts
    """
    identity = build_identity_block(
        agent_name=agent_name,
        description=description,
        run_count=run_count,
        last_run_at_iso=last_run_at_iso,
    )
    return f"{identity}\n\n{AUTO_MEMORY_RULES}".strip()
