"""Centralised Claude model IDs.

Single source of truth for the model strings we pass to the SDK and CLI.
When Anthropic releases a new generation (e.g. Sonnet 4.7), update this
file and everything downstream picks it up.

Use the named constants below — never inline the raw ID string in
business logic. The dashboard/API still accepts the raw IDs for backward
compatibility with old `.md` templates and `.env` overrides.
"""
from __future__ import annotations

# Frontier tier — long-horizon reasoning, architecture, code edits.
OPUS = "claude-opus-4-7"

# Balanced tier — most agent runs, summarisation, structured output.
SONNET = "claude-sonnet-4-6"

# Fast / cheap tier — classification, lightweight rewrites, S1 dispatch.
HAIKU = "claude-haiku-4-5-20251001"
HAIKU_GENERIC = "claude-haiku-4-5"  # alias accepted by the SDK / CLI

# Whitelist exposed to the dashboard's agent form.
ALLOWED_MODELS: tuple[str, ...] = (OPUS, SONNET, HAIKU, HAIKU_GENERIC)

# Task-type aliases (legacy capa-4 selector).
TASK_TYPE_MODELS: dict[str, str] = {
    "fast": HAIKU,
    "think": SONNET,  # placeholder — actually replaced by agent's own model at runtime
    "deep": OPUS,
}
