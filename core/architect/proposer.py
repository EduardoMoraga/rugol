"""Calls claude-agent-sdk with a meta-prompt that designs an agentic stack.

Returns a typed Proposal the dashboard can display, edit, and ship to
the deployer endpoint.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)


META_PROMPT = """You are the Rogologo Architect. A developer comes to you with a one-line idea
and you propose the smallest coherent agentic infrastructure that makes the idea real
on the Rogologo platform — a control plane for Claude Code agents that runs locally on
a Windows PC.

USER'S IDEA
-----------
{idea}

ADDITIONAL CONSTRAINTS
----------------------
{constraints}

WHAT YOU MUST RETURN
--------------------
Reply with one fenced JSON block (```json ... ```) and nothing else outside the fence.
The JSON must validate against this shape:

{{
  "summary": "2-3 sentence summary of what you propose and why this shape (not these words).",
  "rationale": "1-2 paragraphs explaining the trade-offs you took: why this many agents, why these models, what you deliberately did NOT include.",
  "agents": [
    {{
      "name": "lowercase-with-dashes-3-to-40-chars",
      "model": "claude-opus-4-7" | "claude-sonnet-4-6" | "claude-haiku-4-5-20251001",
      "description": "ONE sentence shown on a card — what this agent does, in plain language.",
      "body": "FULL prompt body in markdown, 200-600 words. MUST include sections: '## Who you are', '## When you are invoked', '## What you do, step by step', '## Output format', '## Constraints'. Be specific. Reference concrete tools, formats, cadences."
    }}
  ],
  "skills": [
    {{
      "name": "lowercase-with-dashes",
      "description": "ONE sentence — when to use this skill.",
      "body": "Markdown body that another agent can follow when invoked. 100-300 words."
    }}
  ],
  "schedules": [
    {{
      "agent_name": "must match one of the agents above",
      "cron_expr": "valid 5-field cron expression in UTC, e.g. '0 13 * * 1' for Mondays 1pm UTC",
      "prompt": "What is sent to the agent every time the schedule fires."
    }}
  ],
  "ontology_seeds": [
    {{ "src": "Subject as a short label", "predicate": "verb-with-dashes", "dst": "Object label" }}
  ]
}}

DESIGN RULES
------------
1. **Right-size the team.** Most ideas need 1–3 agents. Five is the upper bound. Each agent must have a sharp, non-overlapping role. If you cannot articulate the role in one sentence, drop the agent.
2. **Pick the right model.** Use claude-sonnet-4-6 by default. Reserve claude-opus-4-7 for genuinely strategic / multi-step reasoning work. Use claude-haiku-4-5-20251001 for routine triage / classification / formatting.
3. **Skills only when reused.** Propose a skill only if (a) two or more agents would invoke it, OR (b) it represents a discrete reusable capability worth naming. Otherwise inline the instruction in the agent's body.
4. **Schedules are optional.** Only propose a schedule when the cadence is obvious from the idea. Do not invent schedules to look thorough.
5. **Ontology seeds are optional.** Useful when the idea has obvious entities/relationships (e.g. "weekly LinkedIn post" → "Eduardo writes-on LinkedIn"). Do not seed generic facts.
6. **No emoji.** No filler. No "leverage" / "synergy" / "robust solution".
7. **Voice in agent bodies.** Direct, second-person, imperative. Tell the agent what it is and what to do. Do not narrate.
8. **Be honest about what won't work yet.** If a part of the idea cannot be done with current tools (e.g. needs an integration Rogologo does not have), call it out in the `rationale`.

Now design the system.
"""


@dataclass
class ProposalAgent:
    name: str
    model: str
    description: str
    body: str


@dataclass
class ProposalSkill:
    name: str
    description: str
    body: str


@dataclass
class ProposalSchedule:
    agent_name: str
    cron_expr: str
    prompt: str


@dataclass
class ProposalTriple:
    src: str
    predicate: str
    dst: str


@dataclass
class Proposal:
    summary: str
    rationale: str
    agents: list[ProposalAgent] = field(default_factory=list)
    skills: list[ProposalSkill] = field(default_factory=list)
    schedules: list[ProposalSchedule] = field(default_factory=list)
    ontology_seeds: list[ProposalTriple] = field(default_factory=list)
    raw_response: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "rationale": self.rationale,
            "agents": [a.__dict__ for a in self.agents],
            "skills": [s.__dict__ for s in self.skills],
            "schedules": [s.__dict__ for s in self.schedules],
            "ontology_seeds": [t.__dict__ for t in self.ontology_seeds],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Proposal":
        return cls(
            summary=str(d.get("summary", "")),
            rationale=str(d.get("rationale", "")),
            agents=[ProposalAgent(**_pick(a, ProposalAgent)) for a in d.get("agents", []) or []],
            skills=[ProposalSkill(**_pick(s, ProposalSkill)) for s in d.get("skills", []) or []],
            schedules=[ProposalSchedule(**_pick(s, ProposalSchedule)) for s in d.get("schedules", []) or []],
            ontology_seeds=[ProposalTriple(**_pick(t, ProposalTriple)) for t in d.get("ontology_seeds", []) or []],
        )


def _pick(d: dict, cls) -> dict:
    """Filter a dict down to fields the dataclass declares — keeps fromdict tolerant."""
    fields = set(cls.__dataclass_fields__)
    return {k: v for k, v in d.items() if k in fields}


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of the model's reply. Tolerant to fences and wrapping prose."""
    if not text or not text.strip():
        raise ValueError("empty response from architect")
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else text
    # If the model omitted the fence, try to find the outermost { ... }.
    if not m:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found in architect response")
        candidate = candidate[start : end + 1]
    return json.loads(candidate)


async def propose(*, idea: str, constraints: str = "", workspace_dir=None) -> Proposal:
    """One-shot call to claude-agent-sdk; parses JSON and returns a Proposal."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as e:
        raise RuntimeError("claude-agent-sdk not installed") from e

    settings = get_settings()
    env = dict(os.environ)
    if settings.USE_SUBSCRIPTION:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    elif settings.ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY

    from pathlib import Path
    workspace = workspace_dir or Path(__file__).resolve().parent.parent.parent

    options = ClaudeAgentOptions(
        cwd=str(workspace),
        model="claude-sonnet-4-6",
        permission_mode="bypassPermissions",
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": "You are operating as the Rogologo Architect — design output only, no tool use, no file writes.",
        },
        setting_sources=[],
        env=env,
    )

    full_prompt = META_PROMPT.format(
        idea=idea.strip() or "(no idea provided)",
        constraints=constraints.strip() or "(none)",
    )

    parts: list[str] = []
    async for message in query(prompt=full_prompt, options=options):
        kind = type(message).__name__
        if kind == "AssistantMessage":
            for block in getattr(message, "content", []) or []:
                btype = getattr(block, "type", None) or type(block).__name__.lower()
                if btype in {"text", "textblock"}:
                    parts.append(getattr(block, "text", "") or "")
        elif kind == "ResultMessage":
            result = getattr(message, "result", None)
            if result and not parts:
                parts.append(str(result))

    raw = "".join(parts).strip()
    data = _extract_json(raw)
    p = Proposal.from_dict(data)
    p.raw_response = raw
    if not p.agents:
        raise ValueError("Architect returned a proposal with zero agents.")
    return p
