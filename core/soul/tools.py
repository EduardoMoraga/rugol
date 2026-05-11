"""SDK MCP tools the agent can call during a run.

The server is built per-run with the agent's name captured in closure.
That guarantees a tool call from agent A can never write to agent B's
memory store — there is no agent_name parameter the agent could spoof.
"""
from __future__ import annotations

import logging
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from core.memory import add_memory, delete_memory, list_memories

logger = logging.getLogger(__name__)

SOUL_MCP_NAME = "rogologo-soul"

# Allow-listed names the runner must include in `allowed_tools` so the
# agent can actually invoke these. Format matches the SDK convention
# `mcp__<server>__<tool>`.
SOUL_TOOL_NAMES: tuple[str, ...] = (
    f"mcp__{SOUL_MCP_NAME}__save_memory",
    f"mcp__{SOUL_MCP_NAME}__list_my_memories",
    f"mcp__{SOUL_MCP_NAME}__forget_memory",
)

_VALID_KINDS = {"user", "feedback", "project", "reference", "note"}


def _text_result(text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": is_error}


def build_soul_mcp_server(agent_name: str) -> McpSdkServerConfig:
    """Build a fresh in-process MCP server for this run.

    Each call captures `agent_name` in a new set of closures, so the
    server returned can only ever read/write the calling agent's store.
    """

    @tool(
        "save_memory",
        "Save a new persistent memory you'll see in every future run. Use "
        "for things future-you should remember: user facts, feedback, "
        "project state, external references. Don't save derivable code "
        "details or ephemeral turn state.",
        {
            "name": str,
            "description": str,
            "content": str,
            "kind": str,
        },
    )
    async def save_memory(args: dict[str, Any]) -> dict[str, Any]:
        try:
            name = (args.get("name") or "").strip()
            description = (args.get("description") or "").strip()
            content = (args.get("content") or "").strip()
            kind = (args.get("kind") or "note").strip().lower()
            if not name or not description or not content:
                return _text_result(
                    "save_memory needs non-empty name, description, and content.",
                    is_error=True,
                )
            if kind not in _VALID_KINDS:
                return _text_result(
                    f"kind must be one of {sorted(_VALID_KINDS)}, got '{kind}'.",
                    is_error=True,
                )
            mem = add_memory(
                agent_name=agent_name,
                name=name,
                description=description,
                content=content,
                kind=kind,
            )
            logger.info("soul: %s saved memory %s (%s)", agent_name, mem.file, kind)
            return _text_result(
                f"Saved memory '{mem.name}' [{mem.kind}] as {mem.file}."
            )
        except Exception as e:
            logger.exception("soul.save_memory failed for %s", agent_name)
            return _text_result(f"save_memory failed: {e}", is_error=True)

    @tool(
        "list_my_memories",
        "List your existing memories. Call this BEFORE save_memory to avoid "
        "duplicating something you already know.",
        {},
    )
    async def list_my_memories(args: dict[str, Any]) -> dict[str, Any]:
        try:
            mems = list_memories(agent_name)
            if not mems:
                return _text_result("(no memories yet)")
            lines = [f"- [{m.kind}] {m.name} — {m.description} ({m.file})" for m in mems]
            return _text_result("\n".join(lines))
        except Exception as e:
            logger.exception("soul.list_my_memories failed for %s", agent_name)
            return _text_result(f"list_my_memories failed: {e}", is_error=True)

    @tool(
        "forget_memory",
        "Delete a memory by filename (e.g. '20260510-user-role.md') or by "
        "its name field. Use when a memory is outdated or wrong — prefer "
        "delete+save over saving a contradictory duplicate.",
        {"file_or_name": str},
    )
    async def forget_memory(args: dict[str, Any]) -> dict[str, Any]:
        try:
            target = (args.get("file_or_name") or "").strip()
            if not target:
                return _text_result("forget_memory needs file_or_name.", is_error=True)
            ok = delete_memory(agent_name, target)
            if not ok:
                return _text_result(
                    f"No memory matched '{target}'. Try list_my_memories first.",
                    is_error=True,
                )
            logger.info("soul: %s forgot memory %s", agent_name, target)
            return _text_result(f"Forgot memory '{target}'.")
        except Exception as e:
            logger.exception("soul.forget_memory failed for %s", agent_name)
            return _text_result(f"forget_memory failed: {e}", is_error=True)

    return create_sdk_mcp_server(
        name=SOUL_MCP_NAME,
        version="1.0.0",
        tools=[save_memory, list_my_memories, forget_memory],
    )
