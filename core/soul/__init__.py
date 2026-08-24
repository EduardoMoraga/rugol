"""Soul Layer — identity, proactive memory, dual-track dispatch, evolutionary archive.

Every agent registered in Rugol inherits these capabilities at run time
without per-agent configuration. See:
- ADR-006: Soul Layer overall.
- ADR-007: Soul-2 dual-track dispatcher.
- ADR-008: Soul-3 evolutionary archive.

Public surface
--------------
- build_soul_context(agent_name, description, run_count)  → str
- La memoria se expone por MCP sobre HTTP (core/mcp/memory_service),
  no por un servidor in-process: los dos motores usan el mismo almacén.
- classify(prompt, agent_name, ...)                       → TrackDecision   (Soul-2)
- model_for_track(track, agent_default_model)             → str             (Soul-2)
- wrap_prompt_for_s2(prompt)                              → str             (Soul-2)
- extract_final_answer(text)                              → str             (Soul-2)
"""
from __future__ import annotations

from core.soul.builder import build_soul_context
from core.soul.checkpoint import run_checkpoint
from core.soul.dispatcher import TrackDecision, classify, model_for_track
from core.soul.plan_then_execute import extract_final_answer, wrap_prompt_for_s2
from core.soul.world_state import build_world_state_block

__all__ = [
    "build_soul_context",
    "classify",
    "TrackDecision",
    "model_for_track",
    "wrap_prompt_for_s2",
    "extract_final_answer",
    "build_world_state_block",
    "run_checkpoint",
]
