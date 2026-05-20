"""SDK MCP tools that expose Honcho shared memory to a running agent.

Unlike `core/soul/tools.py`, these tools are **not** scoped to the calling
agent. The point of Honcho is cross-agent observation: agent A can save an
observation about peer "edu" and agent B can query that same peer minutes
later. The `peer_id` is a tool argument, not a closure.

The MCP server is only built when Honcho is enabled in settings; the
runner skips it otherwise so disabled instances incur zero overhead.
"""
from __future__ import annotations

import logging
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from core.adapters import honcho

logger = logging.getLogger(__name__)

HONCHO_MCP_NAME = "rogologo-honcho"

HONCHO_TOOL_NAMES: tuple[str, ...] = (
    f"mcp__{HONCHO_MCP_NAME}__save_memory",
    f"mcp__{HONCHO_MCP_NAME}__query_memory",
    f"mcp__{HONCHO_MCP_NAME}__search_memory",
)


def _text_result(text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": is_error}


def build_honcho_mcp_server(agent_name: str) -> McpSdkServerConfig:
    """Build the in-process Honcho MCP server.

    `agent_name` is used as the default `peer_id` when a tool call omits it,
    so observations naturally get attributed to whoever is talking.
    """

    @tool(
        "save_memory",
        "Record a durable observation in shared memory. Any agent can later "
        "query it. Use for facts about external peers (users, clients, "
        "teammates) — NOT for things only you should remember (use Soul "
        "save_memory for that). Default peer_id is yourself; pass another "
        "peer_id when the observation is about someone else.",
        {
            "content": str,
            "peer_id": str,
            "session_id": str,
        },
    )
    async def save_memory(args: dict[str, Any]) -> dict[str, Any]:
        try:
            content = (args.get("content") or "").strip()
            peer_id = (args.get("peer_id") or agent_name).strip()
            session_id = (args.get("session_id") or "").strip() or None
            if not content:
                return _text_result("save_memory needs non-empty content.", is_error=True)
            result = honcho.save_observation(
                content=content, peer_id=peer_id, session_id=session_id
            )
            return _text_result(
                f"Saved to peer '{result['peer_id']}' in session '{result['session_id']}'."
            )
        except honcho.HonchoDisabled as e:
            return _text_result(str(e), is_error=True)
        except honcho.HonchoUnavailable as e:
            return _text_result(str(e), is_error=True)
        except Exception as e:
            logger.exception("honcho.save_memory failed")
            return _text_result(f"save_memory failed: {e}", is_error=True)

    @tool(
        "query_memory",
        "Ask a natural-language question about a peer; Honcho synthesises an "
        "answer from everything every agent has observed about them. Use "
        "this BEFORE making assumptions about a known peer — it's cheaper "
        "than asking the user.",
        {
            "query": str,
            "peer_id": str,
        },
    )
    async def query_memory(args: dict[str, Any]) -> dict[str, Any]:
        try:
            query = (args.get("query") or "").strip()
            peer_id = (args.get("peer_id") or "").strip()
            if not query:
                return _text_result("query_memory needs non-empty query.", is_error=True)
            if not peer_id:
                return _text_result(
                    "query_memory needs peer_id (who you're asking about).",
                    is_error=True,
                )
            answer = honcho.query_synthesis(query=query, peer_id=peer_id)
            return _text_result(answer or "(no synthesis returned)")
        except honcho.HonchoDisabled as e:
            return _text_result(str(e), is_error=True)
        except honcho.HonchoUnavailable as e:
            return _text_result(str(e), is_error=True)
        except Exception as e:
            logger.exception("honcho.query_memory failed")
            return _text_result(f"query_memory failed: {e}", is_error=True)

    @tool(
        "search_memory",
        "Semantic search across raw observations (no synthesis). Returns "
        "the top matching snippets verbatim. Use when you need exact "
        "wording, not a summary — e.g. quoting a user's preference back "
        "to them.",
        {
            "query": str,
            "limit": int,
            "session_id": str,
        },
    )
    async def search_memory(args: dict[str, Any]) -> dict[str, Any]:
        try:
            query = (args.get("query") or "").strip()
            limit = int(args.get("limit") or 5)
            session_id = (args.get("session_id") or "").strip() or None
            if not query:
                return _text_result("search_memory needs non-empty query.", is_error=True)
            hits = honcho.search_raw(query=query, limit=limit, session_id=session_id)
            if not hits:
                return _text_result("(no matches)")
            body = "\n".join(f"- {h}" for h in hits)
            return _text_result(body)
        except honcho.HonchoDisabled as e:
            return _text_result(str(e), is_error=True)
        except honcho.HonchoUnavailable as e:
            return _text_result(str(e), is_error=True)
        except Exception as e:
            logger.exception("honcho.search_memory failed")
            return _text_result(f"search_memory failed: {e}", is_error=True)

    return create_sdk_mcp_server(
        name=HONCHO_MCP_NAME,
        version="1.0.0",
        tools=[save_memory, query_memory, search_memory],
    )
