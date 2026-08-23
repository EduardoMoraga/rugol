"""Centralised Claude model IDs.

Single source of truth for the model strings we pass to the SDK and CLI.
When Anthropic releases a new generation, update the three constants below
and everything downstream picks it up.

Use the named constants in business logic — never inline a raw ID string.

Two lists, on purpose:
  - `MODEL_CHOICES` is what the UI and the setup wizard *offer*: the current
    generation only.
  - `ALLOWED_MODELS` is what the API *accepts*: the current generation plus
    every ID we ever shipped, so an agent `.md` written months ago keeps
    saving instead of 400-ing on an edit.
"""
from __future__ import annotations

# Frontier tier — long-horizon reasoning, architecture, code edits.
OPUS = "claude-opus-5"

# Balanced tier — most agent runs, summarisation, structured output.
SONNET = "claude-sonnet-5"

# Fast / cheap tier — classification, lightweight rewrites, S1 dispatch.
HAIKU = "claude-haiku-4-5"

# What the dashboard's agent form and `rugol setup` offer, in tier order.
MODEL_CHOICES: tuple[tuple[str, str], ...] = (
    (SONNET, "Sonnet 5 — equilibrado (recomendado)"),
    (OPUS, "Opus 5 — razonamiento profundo"),
    (HAIKU, "Haiku 4.5 — rápido y barato"),
)

# Superseded IDs we still accept: agents created on earlier versions carry
# these in their frontmatter, and they remain valid model names.
LEGACY_MODELS: tuple[str, ...] = (
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
)

ALLOWED_MODELS: tuple[str, ...] = tuple(m for m, _ in MODEL_CHOICES) + LEGACY_MODELS

# Task-type aliases (legacy capa-4 selector).
TASK_TYPE_MODELS: dict[str, str] = {
    "fast": HAIKU,
    "think": SONNET,  # placeholder — actually replaced by agent's own model at runtime
    "deep": OPUS,
}
