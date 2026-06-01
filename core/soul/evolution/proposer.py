"""Soul-3 mutation proposer (ADR-008).

Generates 1-3 candidate versions of an agent's body, persists them as
proposed lineage entries, and returns the new version ids. Each candidate
carries a rationale ("what I changed") and a hypothesis ("what should
improve").

This is the Soul-3 successor to `core/improvements/reflector.py` —
that file proposes a single diff against an Improvement row. The
proposer writes whole bodies into the lineage, so the diff is implicit
between parent.id and the new version.

The reflector and proposer can coexist; over time the proposer should
absorb the reflector's role and the legacy `improvements` table becomes
read-only history.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy import desc, select

from core.config import get_settings
from core.db import async_session_factory
from core.db.models import Agent, Run
from core.llm_models import OPUS
from core.runner.claude_runner import run_agent
from core.soul.evolution.archive import (
    current_body,
    ensure_archive,
    load_lineage,
    propose_version,
)

logger = logging.getLogger(__name__)


_PROPOSER_META_PROMPT = """You are proposing focused mutations to your own agent spec (your `.md` body).

## Current spec
---
{current_spec}
---

## Your last {n_runs} runs (most recent first)
{run_summary}

## Task
Propose UP TO {max_candidates} candidate mutations. Each candidate is a complete rewrite of the spec body (you may keep most of it the same; just present the full new body). The goal is targeted improvement based on observed behaviour.

For each candidate, output a section delimited by `===CANDIDATE n===` markers:

===CANDIDATE 1===
Hypothesis: <one sentence — what should improve and why>
Rationale: <one sentence — what you changed>
---BODY---
<the FULL new spec body, markdown, no fences>
---END BODY---
===END CANDIDATE 1===

Rules:
- Be surgical. Do not invent capabilities or tools the agent doesn't have.
- Do not change the agent's name or model.
- Keep the body under 4000 characters per candidate.
- If the current spec is already strong, return ZERO candidates and one line: NO_PROPOSALS_NEEDED.
"""


_CAND_RE = re.compile(
    r"===CANDIDATE\s+(\d+)===\s*"
    r"Hypothesis:\s*(.*?)\n"
    r"Rationale:\s*(.*?)\n"
    r"---BODY---\s*(.*?)\s*---END BODY---",
    re.DOTALL | re.IGNORECASE,
)


def _parse_candidates(text: str) -> list[dict]:
    """Pull `===CANDIDATE n===` blocks out of the model's reply."""
    if "NO_PROPOSALS_NEEDED" in (text or ""):
        return []
    out: list[dict] = []
    for m in _CAND_RE.finditer(text or ""):
        _idx, hyp, rat, body = m.groups()
        body = (body or "").strip()
        if not body:
            continue
        out.append({
            "hypothesis": (hyp or "").strip(),
            "rationale": (rat or "").strip(),
            "body": body,
        })
    return out


async def propose_mutations(
    agent_id: int,
    workspace_dir: Path,
    *,
    max_candidates: int = 2,
    n_recent_runs: int = 6,
) -> list[str]:
    """Run reflection on an agent and persist proposed lineage versions.

    Returns the list of newly created version ids (empty when the model
    answered NO_PROPOSALS_NEEDED or the run failed).
    """
    async with async_session_factory() as session:
        agent = await session.get(Agent, agent_id)
        if agent is None:
            return []
        last_runs = (await session.execute(
            select(Run).where(Run.agent_id == agent_id).order_by(desc(Run.id)).limit(n_recent_runs)
        )).scalars().all()
        run_summary = "\n".join(
            f"- run #{r.id} [{r.status}] track={r.track or '-'} cost=${(r.cost_usd or 0):.4f} "
            f"prompt={(r.prompt or '')[:120]!r}"
            for r in last_runs
        ) or "(no past runs)"
        agent_name = agent.name
        agent_body = agent.body or ""

    # Make sure the archive exists so proposals attach to a parent.
    ensure_archive(agent_name, agent_body)
    parent_body = current_body(agent_name, agent_body)

    prompt = _PROPOSER_META_PROMPT.format(
        current_spec=parent_body,
        n_runs=len(last_runs),
        run_summary=run_summary,
        max_candidates=max_candidates,
    )

    try:
        result = await run_agent(
            agent_name="rugol-proposer",
            prompt=prompt,
            workspace_dir=workspace_dir,
            model=OPUS,
        )
    except Exception:
        logger.exception("proposer run failed for agent %s", agent_id)
        return []

    candidates = _parse_candidates(result.final_text)
    if not candidates:
        logger.info("proposer: no candidates for agent %s", agent_name)
        return []

    settings = get_settings()
    multiplier = max(0.0, float(settings.SOUL_PROPOSER_MULTIPLIER))
    keep = max(1, int(round(max_candidates * multiplier)))
    new_ids: list[str] = []
    lineage = load_lineage(agent_name)
    parent_id = lineage.current if lineage else None
    for c in candidates[:keep]:
        vid = propose_version(
            agent_name,
            c["body"],
            rationale=c["rationale"],
            hypothesis=c["hypothesis"],
            parent=parent_id,
        )
        new_ids.append(vid)
    logger.info(
        "proposer: agent=%s created %s proposed versions: %s",
        agent_name, len(new_ids), new_ids,
    )
    return new_ids
