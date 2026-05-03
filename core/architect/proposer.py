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


# Tight prompt — long inputs + long output + Sonnet = slow. The schema is
# kept small; design rules are bullet-form. Bodies capped at 150-300 words.
META_PROMPT = """You are the Rogologo Architect. Given a one-line outcome from a non-technical user, design the smallest coherent agentic system that delivers it on Rogologo (a local Claude Code agent control plane).

The unit of mental account in Rogologo is the PROJECT — a department with a mission and a small team of agents. Always frame your proposal as a project first, then the agents that staff it.

IDEA: {idea}

CONSTRAINTS: {constraints}

Reply with EXACTLY ONE JSON object. No prose around it. May be bare or wrapped in a single ```json fence.

Rules for string values inside the JSON:
- NO triple backticks. Use single backticks for inline code, or describe code blocks in prose.
- Encode literal line breaks as \\n.
- No trailing commas. Double-quote every key.
- Inside example placeholders, use angle-brackets like <date>, never curly braces.

Schema (illustrative; replace every value, drop optional sections you don't use):

  "project": object describing the department this team belongs to:
      "name": short human title in the user's language ("Marca personal", "Hija aprende biología")
      "slug": lowercase, dashes only, 3-40 chars (url-safe; auto-derive from name if unsure)
      "description": one sentence shown on the project card
      "mission": 2-4 sentences the team reads before every run — the WHY behind this department
      "color": hex color that fits the vibe (#7280a8 default if unsure)
      "icon": one lucide icon name from {briefcase, sparkles, heart, rocket, brain, gamepad, users, palette, target, leaf, book-open, headphones}
  "summary": "2-3 sentences on what you propose and why this shape."
  "rationale": "One paragraph: trade-offs taken, what you deliberately did NOT include, what cannot work yet."
  "agents": array of objects with these fields:
      "name": lowercase, dashes only, 3-40 chars
      "model": one of "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"
      "description": one sentence shown on the agent's card
      "body": markdown 150-300 words. Include sections: ## Who you are, ## When you are invoked, ## What you do (numbered steps), ## Output format, ## Constraints. Direct, second-person, imperative. No emoji.
  "skills": array of objects with "name", "description", "body" (100-200 words). Empty array if none.
  "schedules": array of objects with "agent_name" (must match an agent), "cron_expr" (5-field cron in UTC), "prompt". Empty if none.
  "ontology_seeds": array of objects with "src", "predicate", "dst". Empty if none.

Design rules:
- Team size: 1-3 agents typical, 5 max. Each agent has a sharp, non-overlapping role inside the project.
- Models: Sonnet by default. Opus only for real strategic reasoning. Haiku for triage / classification / formatting.
- Skills only when 2+ agents share the capability OR it is a discrete reusable thing worth naming.
- Schedules and ontology_seeds are optional. Do not invent them to look thorough.
- Be honest in `rationale` about what cannot work yet (missing integrations, etc).
- The mission MUST be specific to this project (avoid generic "deliver value" phrasing).

Return the JSON now. No greeting, no commentary, just the object."""


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
class ProposalProject:
    """Project block in an Architect proposal (ADR-005).

    `slug` is auto-derived if blank; `mission` is what the team reads at every
    run as anchor against noise. The deployer creates the project if its slug
    does not exist yet, otherwise reuses it.
    """
    name: str
    slug: str = ""
    description: str = ""
    mission: str = ""
    color: str = "#7280a8"
    icon: str = "briefcase"


@dataclass
class Proposal:
    summary: str
    rationale: str
    project: ProposalProject | None = None
    agents: list[ProposalAgent] = field(default_factory=list)
    skills: list[ProposalSkill] = field(default_factory=list)
    schedules: list[ProposalSchedule] = field(default_factory=list)
    ontology_seeds: list[ProposalTriple] = field(default_factory=list)
    raw_response: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "rationale": self.rationale,
            "project": self.project.__dict__ if self.project else None,
            "agents": [a.__dict__ for a in self.agents],
            "skills": [s.__dict__ for s in self.skills],
            "schedules": [s.__dict__ for s in self.schedules],
            "ontology_seeds": [t.__dict__ for t in self.ontology_seeds],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Proposal":
        proj_raw = d.get("project")
        project = None
        if isinstance(proj_raw, dict) and proj_raw.get("name"):
            project = ProposalProject(**_pick(proj_raw, ProposalProject))
        return cls(
            summary=str(d.get("summary", "")),
            rationale=str(d.get("rationale", "")),
            project=project,
            agents=[ProposalAgent(**_pick(a, ProposalAgent)) for a in d.get("agents", []) or []],
            skills=[ProposalSkill(**_pick(s, ProposalSkill)) for s in d.get("skills", []) or []],
            schedules=[ProposalSchedule(**_pick(s, ProposalSchedule)) for s in d.get("schedules", []) or []],
            ontology_seeds=[ProposalTriple(**_pick(t, ProposalTriple)) for t in d.get("ontology_seeds", []) or []],
        )


def _pick(d: dict, cls) -> dict:
    """Filter a dict down to fields the dataclass declares — keeps fromdict tolerant."""
    fields = set(cls.__dataclass_fields__)
    return {k: v for k, v in d.items() if k in fields}


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of the model's reply.

    Tolerant to:
    - Fenced ```json {...} ``` blocks with backticks INSIDE the JSON strings.
    - Fences with no `json` language hint.
    - Naked JSON with leading or trailing prose.
    - Embedded triple backticks inside string literals.
    """
    if not text or not text.strip():
        raise ValueError("empty response from architect (no text generated)")

    stripped = text.strip()
    fence_inner = _strip_outer_fence(stripped)
    haystack = fence_inner if fence_inner and "{" in fence_inner else stripped

    obj_start = haystack.find("{")
    if obj_start == -1:
        raise ValueError("no '{' found in architect response")
    obj_end = _matching_brace(haystack, obj_start)
    if obj_end == -1:
        obj_end = haystack.rfind("}")
        if obj_end == -1 or obj_end <= obj_start:
            raise ValueError("no balanced JSON object found in architect response")

    candidate = haystack[obj_start : obj_end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        salvaged = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            return json.loads(salvaged)
        except json.JSONDecodeError:
            raise ValueError(
                f"architect produced a malformed JSON object near char {e.pos}: {e.msg}"
            ) from e


def _strip_outer_fence(text: str) -> str:
    if not text.startswith("```"):
        return ""
    first_nl = text.find("\n")
    if first_nl == -1:
        return ""
    inner_start = first_nl + 1
    last_fence = text.rfind("```")
    if last_fence <= inner_start:
        return ""
    return text[inner_start:last_fence].strip()


def _matching_brace(s: str, start: int) -> int:
    """Return the index of the '}' that closes the '{' at `start`, ignoring
    braces inside JSON string literals. -1 if not found.
    """
    depth = 0
    i = start
    in_str = False
    escape = False
    while i < len(s):
        ch = s[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


PROPOSE_TIMEOUT_SECONDS = 180


async def propose(*, idea: str, constraints: str = "", workspace_dir=None) -> Proposal:
    """One-shot call to claude-agent-sdk; parses JSON and returns a Proposal."""
    import asyncio
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
            "append": "You are the Rogologo Architect. Output only the JSON object specified. Do not call tools, do not write files.",
        },
        # Solo "user" — necesitamos las credenciales de subscripción
        # autenticadas en la máquina, pero NO queremos que el Architect
        # vea el CLAUDE.md del repo (lo confundiría sobre el contexto).
        setting_sources=["user"],
        env=env,
    )

    full_prompt = (
        META_PROMPT
        .replace("{idea}", idea.strip() or "(no idea provided)")
        .replace("{constraints}", constraints.strip() or "(none)")
    )

    parts: list[str] = []

    async def _drain():
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

    try:
        await asyncio.wait_for(_drain(), timeout=PROPOSE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise ValueError(
            f"Architect did not finish within {PROPOSE_TIMEOUT_SECONDS}s. "
            f"Tighten the idea or shorten the constraints — the model is taking too long. "
            f"(Got {sum(len(p) for p in parts)} chars so far.)"
        )

    raw = "".join(parts).strip()
    if not raw:
        raise ValueError(
            "Architect returned no text. The Claude CLI may not be authenticated — "
            "run `claude /login` once and retry."
        )
    try:
        data = _extract_json(raw)
    except ValueError as e:
        snippet = raw[:800]
        raise ValueError(f"{e}\n\n--- model said (first 800 chars) ---\n{snippet}") from e
    p = Proposal.from_dict(data)
    p.raw_response = raw
    if not p.agents:
        raise ValueError(
            "Architect returned a proposal with zero agents. Try restating the idea "
            "with a clearer outcome."
        )
    return p
