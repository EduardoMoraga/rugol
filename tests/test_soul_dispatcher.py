"""Soul-2 dispatcher + plan-then-execute tests (ADR-007)."""
from __future__ import annotations

import pytest

from core.soul.dispatcher import (
    TrackDecision,
    _parse_decision,
    classify,
    model_for_track,
)
from core.soul.plan_then_execute import extract_final_answer, wrap_prompt_for_s2


# ---------- _parse_decision ----------

def test_parse_decision_valid_s1():
    raw = '{"track":"s1","confidence":0.92,"rationale":"a greeting"}'
    d = _parse_decision(raw)
    assert d is not None
    assert d.track == "s1"
    assert d.confidence == 0.92
    assert d.rationale == "a greeting"


def test_parse_decision_valid_s2():
    raw = '  {"track": "S2", "confidence": 0.7, "rationale": "design task"}  '
    d = _parse_decision(raw)
    assert d is not None
    assert d.track == "s2"
    assert d.confidence == 0.7


def test_parse_decision_invalid_track():
    raw = '{"track":"banana","confidence":0.5,"rationale":"?"}'
    assert _parse_decision(raw) is None


def test_parse_decision_no_json():
    assert _parse_decision("free-form text, no json") is None


def test_parse_decision_clamps_confidence():
    raw = '{"track":"s1","confidence":2.5,"rationale":"too sure"}'
    d = _parse_decision(raw)
    assert d is not None and d.confidence == 1.0
    raw = '{"track":"s1","confidence":-0.4,"rationale":"too unsure"}'
    d = _parse_decision(raw)
    assert d is not None and d.confidence == 0.0


def test_parse_decision_truncates_rationale():
    raw = '{"track":"s2","confidence":0.5,"rationale":"' + "x" * 400 + '"}'
    d = _parse_decision(raw)
    assert d is not None
    assert len(d.rationale) <= 280


# ---------- classify bypass paths (no LLM call) ----------

@pytest.mark.asyncio
async def test_classify_bypass_when_disabled(monkeypatch):
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_DUAL_TRACK_ENABLED", False, raising=False
    )
    d = await classify("design a database", agent_name="x")
    assert d.bypassed is True
    assert d.track == "s2"


@pytest.mark.asyncio
async def test_classify_bypass_when_empty_prompt():
    d = await classify("", agent_name="x")
    assert d.bypassed is True
    assert d.track == "s2"


@pytest.mark.asyncio
async def test_classify_bypass_when_model_override_fast():
    d = await classify("anything", agent_name="x", model_override="fast")
    assert d.bypassed is True
    assert d.track == "s1"


@pytest.mark.asyncio
async def test_classify_bypass_when_model_override_haiku():
    d = await classify(
        "anything", agent_name="x",
        model_override="claude-haiku-4-5-20251001",
    )
    assert d.bypassed is True
    assert d.track == "s1"


@pytest.mark.asyncio
async def test_classify_bypass_when_model_override_opus():
    d = await classify(
        "anything", agent_name="x",
        model_override="claude-opus-4-7",
    )
    assert d.bypassed is True
    assert d.track == "s2"


# ---------- model_for_track ----------

def test_model_for_track_s1_overrides_to_haiku_only_with_api_key(monkeypatch):
    from core import config
    # With API key auth: S1 routes to Haiku.
    monkeypatch.setattr(
        config.get_settings(), "USE_SUBSCRIPTION", False, raising=False
    )
    assert model_for_track("s1", "claude-opus-4-7") == "claude-haiku-4-5-20251001"


def test_model_for_track_s1_keeps_default_on_subscription(monkeypatch):
    from core import config
    # With subscription (Pro/Max): S1 keeps the agent's model. This avoids
    # the bundled-CLI crash observed when forcing Haiku via subscription.
    monkeypatch.setattr(
        config.get_settings(), "USE_SUBSCRIPTION", True, raising=False
    )
    assert model_for_track("s1", "claude-opus-4-7") == "claude-opus-4-7"


def test_model_for_track_s2_keeps_default():
    assert model_for_track("s2", "claude-opus-4-7") == "claude-opus-4-7"
    assert model_for_track("anything-else", "claude-sonnet-4-6") == "claude-sonnet-4-6"


# ---------- plan_then_execute ----------

def test_wrap_prompt_contains_plan_critique_answer():
    w = wrap_prompt_for_s2("design the database")
    assert "## Plan" in w
    assert "## Critique" in w
    assert "## Answer" in w
    assert "design the database" in w


def test_extract_final_answer_pulls_answer_section():
    text = (
        "## Plan\n- step 1\n- step 2\n- step 3\n\n"
        "## Critique\nMight be slow.\n\n"
        "## Answer\nUse a single Postgres table with a JSONB column.\n"
    )
    assert "Postgres table" in extract_final_answer(text)
    assert "step 1" not in extract_final_answer(text)


def test_extract_final_answer_passthrough_when_no_header():
    text = "Just a regular answer with no scaffolding."
    assert extract_final_answer(text) == text
