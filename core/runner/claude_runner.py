"""Wraps `claude-agent-sdk` subprocess execution.

Streams messages out via the bus while the run is alive. Returns final
result + token usage when ResultMessage is received.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from core.bus import bus
from core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    final_text: str
    session_id: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    files_generated: list[Path] = field(default_factory=list)


def _build_env() -> dict[str, str]:
    """ANTHROPIC_API_KEY removed when USE_SUBSCRIPTION (ADR-002)."""
    settings = get_settings()
    env = dict(os.environ)
    if settings.USE_SUBSCRIPTION:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    elif settings.ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
    return env


SYSTEM_PROMPT_APPEND = """You are running inside Rogologo, a local agent operations platform.

# Output channel
- Your output is rendered both in a web dashboard and (optionally) sent to Telegram/Slack.
- Keep markdown clean; avoid huge tables when the channel is Telegram.
- If you generate files, save them to the workspace and mention paths.
- You may invoke subagents and skills as usual.

# CRITICAL — runtime state is NOT in files
The user can ask you two very different kinds of questions, and the answer source is different for each. Do not confuse them.

(A) Questions about ROGOLOGO ITSELF — schedules, runs, agents, projects, settings, ontology.
- This data lives ONLY in Rogologo's SQLite database. You CANNOT see it by reading files. Files in the filesystem with names like "schedule.py" or "morning_briefing" are scripts of UNRELATED projects belonging to the same user, NOT Rogologo's runtime state.
- The ONLY correct way to answer these questions is via Rogologo's REST API at http://127.0.0.1:8000. Use Bash + curl:
    GET /api/schedules              → list schedules
    GET /api/agents                 → list agents
    GET /api/agents/<id>/source     → agent body + mcp config
    GET /api/projects/<slug>        → project + lessons
    GET /api/settings               → telegram/slack token status
    GET /api/runs?limit=10          → recent runs
- If the API is unreachable for any reason, SAY SO explicitly: "no pude consultar /api/schedules (motivo: ...)". NEVER fabricate a list to fill the gap. NEVER infer schedule names from common patterns (e.g. "Morning Briefing", "Daily Report"). NEVER mix in real company names you know from training data (e.g. "SKF", "Versuni") to make a list look credible.
- Past failure modes this rule explicitly prevents:
    * Reading C:\\...\\some-other-project.py and reporting its hardcoded list as if it were Rogologo's live state.
    * Confabulating a list of schedules with plausible names ("Lucy Morning Briefing", "SKF Daily Reports") when no API call was made.
    * Saying "let me verify" and then producing a confident-sounding table that was never actually verified against /api/schedules.
- Hard rule: if you did not just see a successful HTTP 2xx response from the API in this turn, you DO NOT KNOW the runtime state. Say "no tengo el dato y necesito que el backend esté corriendo en localhost:8000 para consultarlo".

(B) Questions about the USER's WORK — their workspace, clients, files, scripts, notes, anything in their PC.
- For these questions, exploring the filesystem is the WHOLE POINT of Rogologo. Use Read/Bash/Glob/Grep freely against any path the user implicitly or explicitly references.
- Examples that are fully legitimate: "qué tareas tengo de Versuni esta semana" → grep their workspace; "abrí ese script de SKF" → Read directly; "hacé un dashboard con los datos de C:\..." → use the path.
- The user gave the agent broad filesystem access deliberately so the agent can be useful across their actual work, not just Rogologo's internal state.

The single rule: do not confuse the source. Internal state of Rogologo → REST API only. Anything else → filesystem freely.
"""


async def run_agent(
    *,
    agent_name: str,
    prompt: str,
    workspace_dir: Path,
    model: str,
    session_id: str | None = None,
    run_id: int | None = None,
    tools: list[str] | None = None,
    project_context: str | None = None,
    mcp_servers: dict | None = None,
    soul_context: str | None = None,
    soul_mcp_server=None,
    soul_tool_names: tuple[str, ...] = (),
    agent_body: str | None = None,
) -> RunResult:
    """Invoke claude-agent-sdk and stream events while collecting the result.

    `tools`: optional whitelist of built-in tool names. None or empty list
    means "use the full claude_code preset" (Capa 5).

    `project_context`: rendered mission + lessons appended to the system
    prompt so the agent is anchored to its project (Capa 3). Skipped when
    None (e.g. orphan agents).

    `mcp_servers`: per-agent MCP server configurations (Capa 8). Dict keyed
    by server name; values are McpServerConfig (stdio/sse/http). Passed
    straight through to the SDK; ignored when None or empty.

    `soul_context`: identity + auto-memory rules block (ADR-006). Prepended
    to project_context so the agent reads "who am I + how to remember"
    before the project mission.

    `soul_mcp_server`: in-process MCP server exposing save_memory,
    list_my_memories, forget_memory bound to this agent's name. None
    disables the Soul tools for the run.

    `soul_tool_names`: MCP-qualified tool names to add to the allowlist
    when `tools` whitelist is set. Ignored when `tools` is None/empty
    (preset uses every tool anyway).

    `agent_body`: the agent's persona/instructions (the body of its .md
    template, or — when Soul-3 is active — the body of the currently
    selected lineage version). Prepended to the platform rules so the
    model reads "who I am and what I do" before "what the platform expects".
    None falls back to a generic Rogologo agent (no specific persona).
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as e:
        raise RuntimeError(
            "claude-agent-sdk is not installed. Install it with `pip install claude-agent-sdk`."
        ) from e

    # Compose system-prompt append in layers, ordered from "most specific
    # to the agent" → "most specific to the run":
    #   1. agent_body          — the .md persona / current lineage version
    #   2. SYSTEM_PROMPT_APPEND — Rogologo platform rules
    #   3. soul_context         — identity block + auto-memory policy (ADR-006)
    #   4. project_context      — project mission + lessons (ADR-005)
    parts: list[str] = []
    if agent_body and agent_body.strip():
        parts.append(
            "## Agent persona (your spec — what you are, how you work)\n"
            + agent_body.strip()
        )
    parts.append(SYSTEM_PROMPT_APPEND)
    if soul_context:
        parts.append(soul_context)
    if project_context:
        parts.append(project_context)
    system_append = "\n\n".join(parts)

    # `setting_sources=["user"]` — solo necesitamos el "user" setting source
    # para que la SDK use las credenciales de la subscripción Claude Pro/Max
    # autenticada en la máquina (~/.claude/). NO incluimos "project" ni
    # "local" porque eso haría que el agente lea el CLAUDE.md del repo de
    # Rogologo y termine respondiendo como si fuera un dev del repo, en vez
    # de hablar como el agente que el usuario invocó. Bug encontrado al
    # probar un game-designer recién clonado: respondía sobre "Sprint 2 de
    # Rogologo" en vez de sobre juegos educativos.
    options_kwargs: dict = dict(
        cwd=str(workspace_dir),
        model=model,
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code", "append": system_append},
        resume=session_id,
        setting_sources=["user"],
        env=_build_env(),
    )
    # Soul MCP server (ADR-006) — merged into the per-agent mcp_servers
    # map under its own name. Agent-configured servers win on name clash
    # (legacy compat), though `rogologo-soul` is reserved by convention.
    merged_mcp: dict = {}
    if soul_mcp_server is not None:
        merged_mcp["rogologo-soul"] = soul_mcp_server
    if mcp_servers:
        merged_mcp.update(mcp_servers)

    if tools:
        # When the agent has a tool allowlist, surface the soul tools too so
        # the agent can actually call them. Preset mode (no allowlist) opens
        # all tools by default, so we skip the splice there.
        tool_list = list(tools)
        for soul_tool in soul_tool_names:
            if soul_tool not in tool_list:
                tool_list.append(soul_tool)
        options_kwargs["tools"] = tool_list
    if merged_mcp:
        options_kwargs["mcp_servers"] = merged_mcp
    options = ClaudeAgentOptions(**options_kwargs)

    parts: list[str] = []
    new_sid = session_id
    in_tok = out_tok = 0
    cost = 0.0

    async for message in query(prompt=prompt, options=options):
        kind = type(message).__name__

        if kind == "AssistantMessage":
            for block in getattr(message, "content", []) or []:
                btype = getattr(block, "type", None) or type(block).__name__.lower()
                if btype in {"text", "textblock"}:
                    text = getattr(block, "text", "") or ""
                    parts.append(text)
                    await bus.publish("run:message", {
                        "run_id": run_id,
                        "agent": agent_name,
                        "kind": "text",
                        "delta": text,
                    })
                elif btype in {"tool_use", "tooluseblock"}:
                    tool = getattr(block, "name", "?")
                    await bus.publish("run:tool", {
                        "run_id": run_id,
                        "agent": agent_name,
                        "tool": tool,
                    })

        elif kind == "ResultMessage":
            new_sid = getattr(message, "session_id", None) or new_sid
            usage = getattr(message, "usage", None) or {}
            in_tok = int(usage.get("input_tokens", 0) or 0)
            out_tok = int(usage.get("output_tokens", 0) or 0)
            cost = float(getattr(message, "total_cost_usd", 0.0) or 0.0)
            result = getattr(message, "result", None)
            if result and not parts:
                parts.append(str(result))

    final_text = "".join(parts).strip() or "(run completed with no text output)"
    return RunResult(
        final_text=final_text,
        session_id=new_sid,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost,
    )
