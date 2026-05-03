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
- Your output is rendered both in a web dashboard and (optionally) sent to Telegram/Slack.
- Keep markdown clean; avoid huge tables when the channel is Telegram.
- If you generate files, save them to the workspace and mention paths.
- You may invoke subagents and skills as usual.
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
) -> RunResult:
    """Invoke claude-agent-sdk and stream events while collecting the result.

    `tools`: optional whitelist of built-in tool names. None or empty list
    means "use the full claude_code preset" (Capa 5).
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as e:
        raise RuntimeError(
            "claude-agent-sdk is not installed. Install it with `pip install claude-agent-sdk`."
        ) from e

    options_kwargs: dict = dict(
        cwd=str(workspace_dir),
        model=model,
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM_PROMPT_APPEND},
        resume=session_id,
        setting_sources=["user", "project", "local"],
        env=_build_env(),
    )
    if tools:
        options_kwargs["tools"] = list(tools)
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
