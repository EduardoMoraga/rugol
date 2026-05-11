"""Soul-3 candidate validator (ADR-008).

Scores a proposed version against the agent's current version using
self-critique on Opus. Does **not** replay runs by default — replaying
historical prompts requires a curated golden set to score against, which
is out of scope for the first cut. The validator emits a fitness score
in [0, 1] and a rationale; the proposer's score is informational, not
enforcing.

Why we ship without a golden set: a frontier-quality validator needs
ground-truth outcomes (was the answer right? did the user accept it?).
Until enough runs accumulate user-feedback signal, the validator is a
**second opinion**, not a gate. The dashboard surfaces the score; the
human still decides accept/reject/branch.

Future work: replay against a `agent-soul/<agent>/golden_set.jsonl`
file (prompt + accepted_response pairs) and compute response-similarity
or win-rate. The interface here already accepts that path.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from core.runner.claude_runner import run_agent
from core.soul.evolution.archive import (
    archive_dir,
    load_lineage,
    load_version_body,
)

logger = logging.getLogger(__name__)


_VALIDATOR_PROMPT = """You are reviewing a proposed mutation to an agent's spec. Score how likely the candidate is to improve real-world behaviour.

## Current version (baseline)
---
{baseline_body}
---

## Candidate version (proposed mutation)
---
{candidate_body}
---

## Candidate's stated hypothesis
{hypothesis}

## Candidate's stated rationale
{rationale}

## Recent runs (signal about what the agent actually does)
{recent_runs_summary}

## Optional: golden examples (if any)
{golden_section}

## Your task
Produce ONE JSON object on a single line, then nothing else:

{{"score": 0.0..1.0, "verdict": "improve|neutral|regress", "rationale": "<one sentence>", "concerns": ["<short>", "..."]}}

Scoring rubric:
- score > 0.75 → likely improvement, recommend accept.
- 0.4..0.75 → mixed signal; the candidate could go either way, recommend branch (A/B).
- < 0.4 → likely regression, recommend reject.

Be strict. False positives waste the human's attention.
"""


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ValidationResult:
    score: float                     # 0.0 .. 1.0
    verdict: str                     # improve | neutral | regress | unknown
    rationale: str
    concerns: list[str]
    raw: str = ""

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "concerns": list(self.concerns or []),
        }


def _golden_section(agent_name: str) -> str:
    """Render the golden examples file if it exists, else a placeholder."""
    path = archive_dir(agent_name) / "golden_set.jsonl"
    if not path.exists():
        return (
            "(no golden_set.jsonl curated yet — score is based on self-critique only; "
            "treat the result as a second opinion, not a gate)"
        )
    examples: list[str] = []
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            prompt = (row.get("prompt") or "").strip()
            accepted = (row.get("accepted_response") or "").strip()
            if prompt and accepted:
                examples.append(f"### Example {i + 1}\nPrompt: {prompt}\nAccepted reply: {accepted}")
            if len(examples) >= 5:
                break
    except Exception:
        logger.exception("failed to parse golden_set.jsonl for %s", agent_name)
        return "(golden_set.jsonl present but unreadable)"
    if not examples:
        return "(golden_set.jsonl present but empty)"
    return "\n\n".join(examples)


def _parse(raw: str) -> ValidationResult:
    if not raw:
        return ValidationResult(0.5, "unknown", "empty validator output", [], raw="")
    m = _JSON_RE.search(raw)
    if not m:
        return ValidationResult(0.5, "unknown", "validator returned no JSON", [], raw=raw)
    try:
        data = json.loads(m.group(0))
    except Exception:
        return ValidationResult(0.5, "unknown", "validator JSON unparseable", [], raw=raw)
    score = float(data.get("score", 0.5) or 0.5)
    score = max(0.0, min(1.0, score))
    verdict = str(data.get("verdict") or "unknown").lower().strip()
    if verdict not in {"improve", "neutral", "regress", "unknown"}:
        verdict = "unknown"
    rationale = str(data.get("rationale") or "").strip()
    concerns = data.get("concerns") or []
    if not isinstance(concerns, list):
        concerns = [str(concerns)]
    concerns = [str(c).strip() for c in concerns if str(c).strip()]
    return ValidationResult(score=score, verdict=verdict, rationale=rationale, concerns=concerns, raw=raw)


async def validate_candidate(
    agent_name: str,
    version_id: str,
    workspace_dir: Path,
    *,
    recent_runs_summary: str = "",
) -> ValidationResult:
    """Score a proposed version vs the current baseline.

    Returns ValidationResult(score, verdict, rationale, concerns).
    Score is informational: the dashboard surfaces it; humans decide.
    """
    lineage = load_lineage(agent_name)
    if lineage is None:
        return ValidationResult(0.5, "unknown", "no archive for agent", [])
    candidate = lineage.get(version_id)
    if candidate is None:
        return ValidationResult(0.5, "unknown", f"version {version_id} not in archive", [])
    baseline_body = load_version_body(agent_name, lineage.current) or ""
    candidate_body = load_version_body(agent_name, version_id) or ""

    prompt = _VALIDATOR_PROMPT.format(
        baseline_body=baseline_body,
        candidate_body=candidate_body,
        hypothesis=candidate.hypothesis or "(none stated)",
        rationale=candidate.rationale or "(none stated)",
        recent_runs_summary=recent_runs_summary.strip() or "(none provided)",
        golden_section=_golden_section(agent_name),
    )

    try:
        result = await run_agent(
            agent_name="rogologo-validator",
            prompt=prompt,
            workspace_dir=workspace_dir,
            model="claude-opus-4-7",
        )
    except Exception:
        logger.exception("validator run failed for %s/%s", agent_name, version_id)
        return ValidationResult(0.5, "unknown", "validator run failed", [])

    parsed = _parse(result.final_text)
    logger.info(
        "validator: agent=%s version=%s score=%.2f verdict=%s",
        agent_name, version_id, parsed.score, parsed.verdict,
    )
    return parsed
