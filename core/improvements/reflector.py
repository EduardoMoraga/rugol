"""Spawn a reflection job and parse the proposed diff.

The diff is persisted but never applied automatically. Human approval is required.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import desc, select

from core.db import async_session_factory
from core.db.models import Agent, Improvement, Run
from core.runner.claude_runner import run_agent

logger = logging.getLogger(__name__)


META_PROMPT = """You are reviewing your own performance to propose targeted edits to your spec.

Current spec (your `.md`):
---
{current_spec}
---

Your last {n_runs} runs (most recent first):
{run_summary}

Task: propose precise, surgical edits to your spec that would improve future runs.
Constraints:
- Output a unified diff and a 2-sentence rationale.
- Do not invent tools you do not have.
- Do not change your name or model.
- Keep the diff under 30 lines.

Format your response exactly like this:
```diff
<unified diff here>
```

Rationale:
<two sentences>
"""


async def propose_improvement(agent_id: int, workspace_dir: Path) -> int | None:
    """Run reflection and persist a proposed Improvement. Returns improvement_id or None."""
    async with async_session_factory() as session:
        agent = await session.get(Agent, agent_id)
        if agent is None:
            return None

        last_runs = (await session.execute(
            select(Run).where(Run.agent_id == agent_id).order_by(desc(Run.id)).limit(5)
        )).scalars().all()

        run_summary = "\n".join(
            f"- run #{r.id} [{r.status}] prompt={r.prompt[:120]!r}"
            for r in last_runs
        ) or "(no past runs)"

        prompt = META_PROMPT.format(
            current_spec=agent.body,
            n_runs=len(last_runs),
            run_summary=run_summary,
        )

    try:
        result = await run_agent(
            agent_name="rogologo-reflector",
            prompt=prompt,
            workspace_dir=workspace_dir,
            model=agent.model,
        )
    except Exception:
        logger.exception("reflection job failed for agent %s", agent_id)
        return None

    diff, rationale = _parse_response(result.final_text)
    if not diff:
        return None

    async with async_session_factory() as session:
        imp = Improvement(
            agent_id=agent_id,
            proposed_diff_md=diff,
            rationale=rationale or "(no rationale provided)",
            status="proposed",
        )
        session.add(imp)
        await session.commit()
        return imp.id


def _parse_response(text: str) -> tuple[str, str]:
    """Extract `diff` block and trailing rationale lines."""
    diff = ""
    rationale = ""
    if "```diff" in text:
        start = text.find("```diff") + len("```diff")
        end = text.find("```", start)
        if end > start:
            diff = text[start:end].strip()
    if "Rationale:" in text:
        rationale = text.split("Rationale:", 1)[1].strip()
    return diff, rationale
