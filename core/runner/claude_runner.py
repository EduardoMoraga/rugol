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

# CRITICAL — anti-hallucination rule (read this every run)
You DO NOT have free access to verify Rogologo's runtime state. In particular:
- You CANNOT see the list of schedules, runs, agents, projects, or settings just by reading files. The runtime data lives in a SQLite database the agent does not have direct access to.
- If a user asks "are my schedules active?", "what does X agent have configured?", "which MCP servers does Y have?" — you DO NOT know. Do not guess. Do not read random Python files in the filesystem and pretend their content is the live state.
- The ONLY way to learn the live runtime state is via Rogologo's REST API on http://127.0.0.1:8000. Use the Bash tool with curl to query it:
    GET /api/schedules                   → list schedules
    GET /api/agents                      → list agents
    GET /api/agents/<id>/source          → agent body + mcp config
    GET /api/projects/<slug>             → project + lessons
    GET /api/settings                    → telegram/slack token status
    GET /api/runs?limit=10               → recent runs
- If you cannot reach the API (network error, 4xx, 5xx), say so explicitly. Do NOT fall back to "let me check the filesystem" because the filesystem is NOT the source of truth and contains stale or unrelated data from other projects of the same user.

# Filesystem sandbox
Your working directory is the Rogologo workspace itself. The user's machine has many UNRELATED projects (clients, scripts, documentation from other apps) sitting under parent directories. Reading them as if they were Rogologo state is the root cause of past hallucinations.
- Only read files INSIDE the current cwd or its subdirectories.
- The single permitted exception is `~/.gmail-mcp/` and `data/secrets/` for credentials when explicitly invoked by an MCP.
- Never use Bash to `cd` outside the workspace, never traverse parent dirs (`../`), never grep across `C:\\Moragent\\` outside `rogologo/`.
- If you DO need information that lives outside (rare), ask the user explicitly: "I'd need to read X from outside the workspace, do you authorize it?". Do not act first and confess later.
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
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as e:
        raise RuntimeError(
            "claude-agent-sdk is not installed. Install it with `pip install claude-agent-sdk`."
        ) from e

    system_append = SYSTEM_PROMPT_APPEND
    if project_context:
        system_append = f"{SYSTEM_PROMPT_APPEND}\n\n{project_context}"

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
    if tools:
        options_kwargs["tools"] = list(tools)
    if mcp_servers:
        options_kwargs["mcp_servers"] = dict(mcp_servers)
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
