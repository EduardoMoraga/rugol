"""Soul-3 evolutionary archive tests (ADR-008).

Covers archive lifecycle (seed, propose, accept, reject, branch, rollback),
metric folding, and the A/B router. No LLM calls — proposer/validator are
exercised in integration tests with the live SDK.
"""
from __future__ import annotations

import shutil

import pytest

from core.soul.evolution import (
    accept_version,
    active_version_ids,
    archive,
    branch_to,
    current_body,
    ensure_archive,
    list_versions,
    load_lineage,
    pick_version_for_run,
    propose_version,
    record_metrics,
    reject_version,
    rollback_to,
)
from core.soul.evolution.archive import archive_dir


AGENT = "test-soul-evolution-agent"


@pytest.fixture(autouse=True)
def _clean_archive():
    d = archive_dir(AGENT)
    if d.exists():
        shutil.rmtree(d)
    yield
    if d.exists():
        shutil.rmtree(d)


# ---------- ensure_archive ----------

def test_ensure_archive_creates_001_when_missing():
    body = "You are X. You do Y."
    lineage = ensure_archive(AGENT, body)
    assert lineage.current == "001"
    assert len(lineage.versions) == 1
    assert lineage.versions[0].id == "001"
    assert lineage.versions[0].status == "active"
    assert current_body(AGENT, "fallback") == body + "\n"


def test_ensure_archive_idempotent():
    ensure_archive(AGENT, "first body")
    second = ensure_archive(AGENT, "second body")  # body argument ignored
    assert len(second.versions) == 1
    assert current_body(AGENT, "fallback").startswith("first body")


# ---------- propose / accept / reject ----------

def test_propose_creates_next_id_with_parent():
    ensure_archive(AGENT, "v1 body")
    vid = propose_version(
        AGENT, "v2 body",
        rationale="tightened tone",
        hypothesis="shorter replies",
    )
    assert vid == "002"
    versions = list_versions(AGENT)
    assert len(versions) == 2
    proposed = versions[1]
    assert proposed.status == "proposed"
    assert proposed.parent == "001"
    assert proposed.rationale == "tightened tone"
    assert proposed.hypothesis == "shorter replies"


def test_propose_with_no_archive_seeds_then_proposes():
    vid = propose_version(AGENT, "body proposed first")
    versions = list_versions(AGENT)
    assert {v.id for v in versions} == {"001", "002"}
    assert vid == "002"


def test_accept_sets_current_and_archives_siblings():
    ensure_archive(AGENT, "v1 body")
    vid = propose_version(AGENT, "v2 body")
    accepted = accept_version(AGENT, vid)
    assert accepted
    lin = load_lineage(AGENT)
    assert lin.current == vid
    v1 = lin.get("001")
    v2 = lin.get(vid)
    assert v1.status == "archived"
    assert v2.status == "active"


def test_reject_only_marks_status():
    ensure_archive(AGENT, "v1 body")
    vid = propose_version(AGENT, "v2 body")
    assert reject_version(AGENT, vid)
    lin = load_lineage(AGENT)
    assert lin.current == "001"
    assert lin.get(vid).status == "rejected"


def test_accept_returns_false_for_unknown_version():
    ensure_archive(AGENT, "v1 body")
    assert accept_version(AGENT, "999") is False


# ---------- branch (A/B) ----------

def test_branch_keeps_current_active_alongside_candidate():
    ensure_archive(AGENT, "v1 body")
    vid = propose_version(AGENT, "v2 body")
    assert branch_to(AGENT, vid)
    lin = load_lineage(AGENT)
    assert lin.current == "001"  # current unchanged
    statuses = {v.id: v.status for v in lin.versions}
    assert statuses["001"] == "active"
    assert statuses[vid] == "active"
    assert set(active_version_ids(AGENT)) == {"001", vid}


# ---------- rollback ----------

def test_rollback_to_archives_newer_versions():
    ensure_archive(AGENT, "v1 body")
    v2 = propose_version(AGENT, "v2 body")
    accept_version(AGENT, v2)
    v3 = propose_version(AGENT, "v3 body")
    accept_version(AGENT, v3)
    assert load_lineage(AGENT).current == v3
    # Roll back to v2
    assert rollback_to(AGENT, v2)
    lin = load_lineage(AGENT)
    assert lin.current == v2
    assert lin.get(v3).status == "archived"


# ---------- record_metrics ----------

def test_record_metrics_folds_average():
    ensure_archive(AGENT, "v1 body")
    record_metrics(AGENT, "001", cost_usd=0.10, latency_ms=1000)
    record_metrics(AGENT, "001", cost_usd=0.20, latency_ms=2000)
    lin = load_lineage(AGENT)
    v = lin.get("001")
    assert v.metrics["runs"] == 2
    assert abs(v.metrics["avg_cost_usd"] - 0.15) < 1e-6
    assert abs(v.metrics["avg_latency_ms"] - 1500) < 1e-6


def test_record_metrics_no_op_on_missing_version():
    # Does not raise even with no archive.
    record_metrics(AGENT, "999", cost_usd=1.0)


# ---------- router ----------

def test_router_returns_none_when_no_archive():
    assert pick_version_for_run(AGENT, run_id=1) is None


def test_router_returns_current_when_ab_disabled(monkeypatch):
    ensure_archive(AGENT, "v1 body")
    v2 = propose_version(AGENT, "v2 body")
    branch_to(AGENT, v2)
    # AB disabled: always current
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_EVOLUTION_AB_ENABLED", False, raising=False
    )
    assert pick_version_for_run(AGENT, run_id=42) == "001"


def test_router_rotates_when_ab_enabled(monkeypatch):
    ensure_archive(AGENT, "v1 body")
    v2 = propose_version(AGENT, "v2 body")
    branch_to(AGENT, v2)
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_EVOLUTION_AB_ENABLED", True, raising=False
    )
    # active is ["001", v2], pivot = run_id % 2
    picks = {pick_version_for_run(AGENT, run_id=i) for i in range(10)}
    assert picks == {"001", v2}
