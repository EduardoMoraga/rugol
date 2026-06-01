"""Soul Layer tests (ADR-006).

Covers:
- identity block renders for new and seasoned agents
- auto-memory rules are present and mention the four kinds
- soul context composes both pieces
- soul MCP server exposes the three tools by name
- save_memory tool writes a real file via the existing memory store
- list_my_memories surfaces what was just saved
- forget_memory removes it
"""
from __future__ import annotations

import shutil

import pytest

from core.memory import memory_dir
from core.soul import SOUL_TOOL_NAMES, build_soul_context, build_soul_mcp_server
from core.soul.auto_memory import AUTO_MEMORY_RULES
from core.soul.identity import build_identity_block


AGENT = "test-soul-agent"


@pytest.fixture(autouse=True)
def _clean_agent_memory():
    """Each test starts with no memory for the test agent."""
    d = memory_dir(AGENT)
    if d.exists():
        shutil.rmtree(d)
    yield
    if d.exists():
        shutil.rmtree(d)


def test_identity_block_fresh_agent():
    block = build_identity_block(AGENT, "A test agent.", run_count=0)
    assert AGENT in block
    assert "A test agent." in block
    # Fresh agent → no Historial line
    assert "Historial" not in block


def test_identity_block_seasoned_agent():
    block = build_identity_block(
        AGENT, "A test agent.", run_count=12, last_run_at_iso="2026-05-10T09:00:00+00:00"
    )
    assert "12 run" in block
    assert "2026-05-10T09:00:00+00:00" in block


def test_identity_block_truncates_long_description():
    long_desc = "x" * 500
    block = build_identity_block(AGENT, long_desc)
    assert "…" in block or len(block) < 600


def test_auto_memory_rules_mention_four_kinds():
    rules = AUTO_MEMORY_RULES
    for kind in ("user", "feedback", "project", "reference"):
        assert kind in rules, f"auto-memory rules missing kind: {kind}"
    # And the three tools
    for tool in ("save_memory", "list_my_memories", "forget_memory"):
        assert tool in rules


def test_soul_context_composes_identity_and_rules():
    ctx = build_soul_context(AGENT, "desc", run_count=1)
    assert "Tu identidad" in ctx
    assert "Cómo usar tu memoria persistente" in ctx


def test_soul_tool_names_match_mcp_convention():
    assert len(SOUL_TOOL_NAMES) == 3
    for name in SOUL_TOOL_NAMES:
        assert name.startswith("mcp__rugol-soul__")


def test_soul_mcp_server_structure():
    server = build_soul_mcp_server(AGENT)
    assert server["type"] == "sdk"
    assert server["name"] == "rugol-soul"
    assert server["instance"] is not None


@pytest.mark.asyncio
async def test_save_then_list_then_forget_via_tools():
    """End-to-end: build the server, fish out the three handlers, exercise them."""
    server = build_soul_mcp_server(AGENT)
    instance = server["instance"]

    # The MCP Server stores handlers in request_handlers keyed by request type.
    # Easiest path: ask the registered list_tools handler then invoke call_tool.
    from mcp.types import CallToolRequest, ListToolsRequest

    # We don't go through the request_handlers plumbing — too coupled to MCP
    # internals. Instead we re-build a quick way to invoke each by name
    # through the public attribute set up by create_sdk_mcp_server.
    #
    # The cleanest path that works across MCP versions: call the handlers
    # registered on the instance via _request_handlers (private but stable).
    handlers = getattr(instance, "request_handlers", None)
    assert handlers is not None, "MCP server should expose request_handlers"

    list_handler = handlers[ListToolsRequest]
    call_handler = handlers[CallToolRequest]

    list_req = ListToolsRequest(method="tools/list")
    list_result = await list_handler(list_req)
    tool_names = {t.name for t in list_result.root.tools}
    assert tool_names == {"save_memory", "list_my_memories", "forget_memory"}

    async def call(name: str, args: dict) -> str:
        req = CallToolRequest(
            method="tools/call",
            params={"name": name, "arguments": args},
        )
        res = await call_handler(req)
        # ServerResult wraps a CallToolResult; flatten text content for asserts
        inner = res.root
        return "\n".join(getattr(c, "text", "") for c in inner.content)

    # SAVE
    out = await call("save_memory", {
        "name": "test pref",
        "description": "Likes succinct answers",
        "content": "User prefers short, direct responses.",
        "kind": "feedback",
    })
    assert "Saved memory" in out

    # LIST
    out = await call("list_my_memories", {})
    assert "test pref" in out
    assert "feedback" in out

    # FORGET (by name)
    out = await call("forget_memory", {"file_or_name": "test pref"})
    assert "Forgot memory" in out

    # LIST again → empty
    out = await call("list_my_memories", {})
    assert "no memories yet" in out


@pytest.mark.asyncio
async def test_save_memory_rejects_invalid_kind():
    server = build_soul_mcp_server(AGENT)
    instance = server["instance"]
    from mcp.types import CallToolRequest

    handlers = instance.request_handlers
    call_handler = handlers[CallToolRequest]

    req = CallToolRequest(
        method="tools/call",
        params={
            "name": "save_memory",
            "arguments": {
                "name": "x",
                "description": "y",
                "content": "z",
                "kind": "garbage",
            },
        },
    )
    res = await call_handler(req)
    inner = res.root
    assert inner.isError is True
    text = "\n".join(getattr(c, "text", "") for c in inner.content)
    assert "kind must be one of" in text


@pytest.mark.asyncio
async def test_save_memory_rejects_empty_fields():
    server = build_soul_mcp_server(AGENT)
    instance = server["instance"]
    from mcp.types import CallToolRequest

    call_handler = instance.request_handlers[CallToolRequest]

    req = CallToolRequest(
        method="tools/call",
        params={
            "name": "save_memory",
            "arguments": {
                "name": "",
                "description": "y",
                "content": "z",
                "kind": "user",
            },
        },
    )
    res = await call_handler(req)
    inner = res.root
    assert inner.isError is True
