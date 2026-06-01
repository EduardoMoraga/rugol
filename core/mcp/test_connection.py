"""Test that an MCP server actually starts and responds to the JSON-RPC handshake.

Standalone — does not depend on claude-agent-sdk. Spawns the configured
subprocess, performs `initialize` + `tools/list`, returns the discovered
tools or a structured error.

Why this exists
---------------
Before this module, configuring an MCP server in Rugol was a leap of
faith: you pasted command/args/env in the UI, saved, and the only way to
know if it worked was to invoke the agent and watch logs. If `npx -y
some-pkg` failed because the package was unpublished, or env vars were
missing, you had no signal in the UI. This wasted hours debugging YouTube
MCP and Slack adapter in the v0.5 → v0.6 sessions.

The endpoint is deliberately conservative: 8 second timeout, hard kill on
exit, never trusts the subprocess to clean up.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Conservative — stdio MCP servers usually answer in <2s once the binary
# is cached. The first run may pay an `npx` install cost; we cap that at
# 8s so the UI doesn't hang the user.
HANDSHAKE_TIMEOUT_S = 8.0
KILL_GRACE_S = 1.5


@dataclass
class McpTestResult:
    ok: bool
    tools: list[str] = field(default_factory=list)  # tool names discovered
    error: str | None = None
    error_kind: str | None = None  # "not_installed" | "timeout" | "bad_response" | "stderr" | "spawn_failed"
    stderr_tail: str | None = None  # last ~600 chars of stderr if present
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tools": self.tools,
            "error": self.error,
            "error_kind": self.error_kind,
            "stderr_tail": self.stderr_tail,
            "duration_ms": self.duration_ms,
        }


def _build_env(extra: dict[str, str] | None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        for k, v in extra.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = str(v)
    return env


async def _read_until_response(stream: asyncio.StreamReader, target_id: int, deadline: float) -> dict | None:
    """Read JSON-RPC line-delimited messages until we see one with the target id."""
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return None
        try:
            line = await asyncio.wait_for(stream.readline(), timeout=remaining)
        except asyncio.TimeoutError:
            return None
        if not line:
            return None  # EOF
        try:
            msg = json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            # Some servers print a banner before speaking JSON-RPC.
            continue
        if isinstance(msg, dict) and msg.get("id") == target_id:
            return msg


async def _drain_stderr(proc: asyncio.subprocess.Process, max_bytes: int = 4096) -> str:
    """Best-effort: read whatever stderr has produced by now, non-blocking."""
    if proc.stderr is None:
        return ""
    chunks: list[bytes] = []
    total = 0
    try:
        while total < max_bytes:
            try:
                chunk = await asyncio.wait_for(proc.stderr.read(1024), timeout=0.05)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except Exception:
        pass
    text = b"".join(chunks).decode("utf-8", errors="replace")
    return text[-600:] if len(text) > 600 else text


async def test_mcp_server(*, command: str, args: list[str], env: dict[str, str] | None) -> McpTestResult:
    """Spawn a stdio MCP server, do `initialize` + `tools/list`, return discovered tools.

    Never raises. All failures are returned as McpTestResult(ok=False, ...).
    """
    started = asyncio.get_event_loop().time()
    full_env = _build_env(env)

    # Sanitize args: must be a flat list of strings.
    args_list = [str(a) for a in (args or []) if str(a).strip()]

    try:
        proc = await asyncio.create_subprocess_exec(
            command,
            *args_list,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
    except FileNotFoundError as e:
        return McpTestResult(
            ok=False,
            error_kind="spawn_failed",
            error=f"Command not found: {command}. Verifica que esté instalado y en PATH.",
            duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
        )
    except Exception as e:
        logger.exception("mcp test spawn failed")
        return McpTestResult(
            ok=False,
            error_kind="spawn_failed",
            error=f"No pude iniciar el subprocess: {e!s}",
            duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
        )

    deadline = asyncio.get_event_loop().time() + HANDSHAKE_TIMEOUT_S

    async def _send(msg: dict) -> None:
        if proc.stdin is None:
            raise RuntimeError("stdin closed")
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        proc.stdin.write(line.encode("utf-8"))
        await proc.stdin.drain()

    try:
        # 1) initialize
        await _send({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "rugol-mcp-tester", "version": "0.6"},
            },
        })

        if proc.stdout is None:
            stderr_tail = await _drain_stderr(proc)
            return McpTestResult(
                ok=False,
                error_kind="bad_response",
                error="El subprocess no expone stdout — probablemente falló al cargar el módulo MCP.",
                stderr_tail=stderr_tail or None,
                duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            )

        init_resp = await _read_until_response(proc.stdout, 1, deadline)
        if init_resp is None:
            stderr_tail = await _drain_stderr(proc)
            kind = "timeout" if proc.returncode is None else "not_installed"
            err_msg = (
                "El servidor MCP no respondió a `initialize` en 8 s. "
                "Causas frecuentes: el paquete npm no se pudo descargar, "
                "el binario no expone CLI, o falta una variable de entorno crítica."
            )
            if stderr_tail:
                err_msg += f"\n\nstderr:\n{stderr_tail}"
            return McpTestResult(
                ok=False,
                error_kind=kind,
                error=err_msg,
                stderr_tail=stderr_tail or None,
                duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            )

        if "error" in init_resp:
            stderr_tail = await _drain_stderr(proc)
            return McpTestResult(
                ok=False,
                error_kind="bad_response",
                error=f"El MCP rechazó initialize: {init_resp['error']}",
                stderr_tail=stderr_tail or None,
                duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            )

        # 2) initialized notification (no id, no response expected)
        await _send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 3) tools/list
        await _send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools_resp = await _read_until_response(proc.stdout, 2, deadline)
        if tools_resp is None:
            stderr_tail = await _drain_stderr(proc)
            return McpTestResult(
                ok=False,
                error_kind="timeout",
                error="`tools/list` no respondió en el tiempo restante.",
                stderr_tail=stderr_tail or None,
                duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            )

        if "error" in tools_resp:
            return McpTestResult(
                ok=False,
                error_kind="bad_response",
                error=f"El MCP rechazó tools/list: {tools_resp['error']}",
                duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            )

        tools_payload = (tools_resp.get("result") or {}).get("tools") or []
        tool_names = [t.get("name") for t in tools_payload if isinstance(t, dict) and t.get("name")]

        return McpTestResult(
            ok=True,
            tools=tool_names,
            duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
        )

    finally:
        # Always tear down the subprocess.
        try:
            if proc.stdin and not proc.stdin.is_closing():
                proc.stdin.close()
        except Exception:
            pass
        if proc.returncode is None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=KILL_GRACE_S)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
            except ProcessLookupError:
                pass
            except Exception:
                logger.exception("error tearing down mcp test subprocess")
