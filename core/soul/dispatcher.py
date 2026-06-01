"""Soul-2 dual-track dispatcher (ADR-007).

Classifies an incoming prompt as System 1 (intuitive / cheap) or System 2
(deliberate / expensive) before model selection.

The classifier itself runs on Haiku — the prompt is fixed (cacheable) and
the user content is short, so the cost is negligible (fractions of a cent
per call). On a parse failure we **default to S2**: better to spend more
than to ship a sloppy answer.

The dispatcher does NOT execute the task; it only decides the track and
returns metadata. The orchestrator wires the decision back into
`model_override`, prompt construction, and the Run row.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

from core.config import get_settings
from core.llm_models import HAIKU

logger = logging.getLogger(__name__)


_CLASSIFIER_SYSTEM_PROMPT = """You are Rugol's dispatcher. You classify ONE incoming request into S1 or S2.

S1 (System 1 — fast, intuitive, cheap):
- Greetings, casual chat, status questions, acknowledgements.
- Restating, light reformatting, single-fact recall the agent already knows.
- Anything an attentive person could answer in <10 seconds without deliberation.

S2 (System 2 — slow, deliberate, expensive):
- Multi-step planning, code edits, design decisions, architecture.
- Reasoning under uncertainty, weighing tradeoffs, research.
- Anything where being wrong has real cost.

When uncertain, return S2. confidence above 0.85 only if it's clearly one.

Respond with EXACTLY one JSON object on a single line, nothing else:
{"track":"s1","confidence":0.91,"rationale":"single sentence"}

Allowed track values: "s1" or "s2".
confidence is a float 0..1.
rationale is one short sentence (<140 chars).
"""


_JSON_LINE_RE = re.compile(r"\{.*?\}", re.DOTALL)


@dataclass
class TrackDecision:
    track: str               # "s1" | "s2"
    confidence: float        # 0.0 .. 1.0
    rationale: str           # one short sentence
    bypassed: bool = False   # True when we skipped the classifier (returns default S2)


def _build_env() -> dict[str, str]:
    """Same envelope as claude_runner._build_env, but local to avoid coupling."""
    settings = get_settings()
    env = dict(os.environ)
    if settings.USE_SUBSCRIPTION:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    elif settings.ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
    return env


def _parse_decision(raw: str) -> TrackDecision | None:
    """Pull the first JSON-looking object out of the model's reply."""
    if not raw:
        return None
    m = _JSON_LINE_RE.search(raw)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    track = str(data.get("track", "")).strip().lower()
    if track not in {"s1", "s2"}:
        return None
    try:
        conf = float(data.get("confidence", 0.5))
    except Exception:
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    rat = str(data.get("rationale", "") or "").strip()
    if len(rat) > 280:
        rat = rat[:277].rstrip() + "…"
    return TrackDecision(track=track, confidence=conf, rationale=rat or "(no rationale)")


_FALLBACK = TrackDecision(
    track="s2",
    confidence=0.5,
    rationale="dispatcher fallback — when uncertain, prefer deliberate.",
    bypassed=False,
)


async def classify(
    prompt: str,
    agent_name: str | None = None,
    *,
    model_override: str | None = None,
    workspace_dir=None,
) -> TrackDecision:
    """Run the classifier and return a TrackDecision.

    Bypasses (returns bypassed=True with S2 default) when:
    - settings.SOUL_DUAL_TRACK_ENABLED is False
    - the caller already forced model_override (the human chose the track)
    - the prompt is empty
    """
    settings = get_settings()

    if not settings.SOUL_DUAL_TRACK_ENABLED or not (prompt or "").strip():
        return TrackDecision(
            track="s2", confidence=0.0,
            rationale="dispatcher disabled or empty prompt", bypassed=True,
        )
    if model_override:
        # Caller explicitly chose a track via fast/deep — respect it.
        track = "s1" if str(model_override).lower() == "fast" or "haiku" in str(model_override).lower() else "s2"
        return TrackDecision(
            track=track, confidence=1.0,
            rationale=f"caller forced model_override={model_override}", bypassed=True,
        )

    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError:
        logger.warning("claude-agent-sdk not installed, dispatcher returns fallback")
        return _FALLBACK

    user_prompt = (
        f"Classify this incoming request for agent '{agent_name or '?'}':\n\n"
        f"---\n{prompt.strip()}\n---"
    )

    options = ClaudeAgentOptions(
        model=settings.SOUL_CLASSIFIER_MODEL,
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code", "append": _CLASSIFIER_SYSTEM_PROMPT},
        setting_sources=["user"],
        env=_build_env(),
    )
    if workspace_dir is not None:
        options.cwd = str(workspace_dir)

    parts: list[str] = []
    try:
        async for message in query(prompt=user_prompt, options=options):
            kind = type(message).__name__
            if kind == "AssistantMessage":
                for block in getattr(message, "content", []) or []:
                    btype = getattr(block, "type", None) or type(block).__name__.lower()
                    if btype in {"text", "textblock"}:
                        parts.append(getattr(block, "text", "") or "")
    except Exception:
        logger.exception("dispatcher classification failed for agent %s", agent_name)
        return _FALLBACK

    raw = "".join(parts).strip()
    parsed = _parse_decision(raw)
    if parsed is None:
        logger.warning("dispatcher could not parse '%s' — falling back to S2", raw[:200])
        return _FALLBACK
    logger.info(
        "dispatcher: agent=%s track=%s confidence=%.2f rationale=%s",
        agent_name, parsed.track, parsed.confidence, parsed.rationale,
    )
    return parsed


def model_for_track(track: str, agent_default_model: str) -> str:
    """Resolve which model to use given a track.

    Convention:
    - s1 → Haiku 4.5 ONLY when running via API key. With subscription
      auth (Pro/Max), Haiku via the bundled CLI subprocess crashes
      (exit code 1, observed 2026-05-10 with agent=gugol). Until we
      identify the root cause, S1 with subscription keeps the agent's
      default model — the routing still has value (telemetry, future
      prompt caching) without the model swap risk.
    - s2 → the agent's configured default model.
    """
    if track == "s1":
        settings = get_settings()
        if settings.USE_SUBSCRIPTION:
            # Avoid the Haiku-on-subscription crash. Telemetry still
            # records the run as 's1'.
            return agent_default_model
        return HAIKU
    return agent_default_model
