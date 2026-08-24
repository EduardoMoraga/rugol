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


# ── Modelos por motor ────────────────────────────────────────────────────────
# Cambiar de motor no puede costar la corrida. Antes, un agente con
# `model: gpt-5.6-luna` que pasaba a Claude fallaba con "issue with the selected
# model", y al revés Codex rechazaba un id de Claude. Ahora el modelo se traduce
# por NIVEL, que es la intención real del usuario: si elegiste el rápido, seguís
# en el rápido.

# Nivel → (modelo Claude, modelo Codex). Verificado contra
# ~/.codex/models_cache.json de codex-cli 0.149.0.
TIERS: dict[str, dict[str, str]] = {
    "frontier": {"claude": OPUS, "codex": "gpt-5.6-sol"},
    "balanced": {"claude": SONNET, "codex": "gpt-5.6-terra"},
    "fast": {"claude": HAIKU, "codex": "gpt-5.6-luna"},
}

# Lo que ofrece la UI para cada motor, en orden de nivel.
ENGINE_MODEL_CHOICES: dict[str, tuple[tuple[str, str], ...]] = {
    "claude": (
        (SONNET, "Sonnet 5 — equilibrado (recomendado)"),
        (OPUS, "Opus 5 — razonamiento profundo"),
        (HAIKU, "Haiku 4.5 — rápido y barato"),
    ),
    "codex": (
        ("gpt-5.6-terra", "GPT-5.6 Terra — equilibrado (recomendado)"),
        ("gpt-5.6-sol", "GPT-5.6 Sol — frontera, agéntico"),
        ("gpt-5.6-luna", "GPT-5.6 Luna — rápido y barato"),
        ("gpt-5.5", "GPT-5.5 — frontera anterior"),
        ("gpt-5.4-mini", "GPT-5.4 Mini — el más económico"),
    ),
}

ENGINE_DEFAULT_MODEL: dict[str, str] = {
    "claude": SONNET,
    "codex": "gpt-5.6-terra",
}


def tier_of(model: str) -> str | None:
    """A qué nivel pertenece un modelo, sin importar el motor."""
    for tier, per_engine in TIERS.items():
        if model in per_engine.values():
            return tier
    # Generaciones anteriores de Claude, por su nombre de familia.
    lowered = (model or "").lower()
    if "opus" in lowered:
        return "frontier"
    if "sonnet" in lowered:
        return "balanced"
    if "haiku" in lowered:
        return "fast"
    return None


def belongs_to(model: str, engine: str) -> bool:
    if not model:
        return False
    if engine == "claude":
        return model.startswith("claude-")
    if engine == "codex":
        return model.startswith(("gpt-", "o1", "o3", "codex-"))
    return False


def resolve_model(engine: str, model: str | None) -> str:
    """El modelo que hay que pasarle a `engine`, respetando el nivel elegido.

    - Si el modelo ya es de ese motor, se usa tal cual.
    - Si es de otro motor, se traduce al equivalente del mismo nivel.
    - Si no se puede inferir el nivel, se usa el default del motor.
    """
    engine = engine if engine in ENGINE_DEFAULT_MODEL else "claude"
    if model and belongs_to(model, engine):
        return model
    tier = tier_of(model or "")
    if tier:
        return TIERS[tier][engine]
    return ENGINE_DEFAULT_MODEL[engine]
