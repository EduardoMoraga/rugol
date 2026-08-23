"""Locate the Claude Code CLI Rugol actually runs, and read its auth state.

Rugol never talks to the Anthropic API directly: every run shells out to the
Claude Code CLI through `claude-agent-sdk`. The wheel ships its own CLI binary
under `claude_agent_sdk/_bundled/`, and the SDK prefers it over anything on
PATH — so "is the `claude` in my terminal logged in?" is the wrong question.
The only binary that matters is the one resolved here.

This module is the single source of truth for that resolution, shared by:
  - `GET /api/health/auth` (dashboard + doctor)
  - `cli/rugol-auth.py`   (`rugol login` / `logout` / `doctor`)

Resolution order mirrors the SDK's own `_find_cli`, so what we report is what
a run will use.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STATUS_TTL_SECONDS = 60.0
_cached_status: tuple[float, dict[str, Any]] | None = None


def _bundled_cli() -> str | None:
    """The CLI shipped inside the claude-agent-sdk wheel (~200 MB, platform-tagged)."""
    try:
        import claude_agent_sdk
    except ImportError:
        return None
    pkg_dir = Path(claude_agent_sdk.__file__).resolve().parent
    name = "claude.exe" if platform.system() == "Windows" else "claude"
    candidate = pkg_dir / "_bundled" / name
    return str(candidate) if candidate.is_file() else None


def find_cli() -> tuple[str | None, str]:
    """Return (path, source). `source` is one of bundled | path | wellknown | none."""
    if bundled := _bundled_cli():
        return bundled, "bundled"
    if found := shutil.which("claude"):
        return found, "path"
    home = Path.home()
    for candidate in (
        home / ".npm-global/bin/claude",
        Path("/usr/local/bin/claude"),
        home / ".local/bin/claude",
        home / "node_modules/.bin/claude",
        home / ".yarn/bin/claude",
        home / ".claude/local/claude",
    ):
        if candidate.is_file():
            return str(candidate), "wellknown"
    return None, "none"


def cli_version(cli_path: str) -> str:
    try:
        out = subprocess.run(
            [cli_path, "--version"],
            capture_output=True, text=True, timeout=30,
        )
        return (out.stdout or out.stderr).strip().splitlines()[0] if out.stdout or out.stderr else ""
    except Exception:
        return ""


def _run_env() -> dict[str, str]:
    """The exact environment a run gets, so we report what runs actually see."""
    from core.runner.claude_runner import _build_env
    return _build_env()


def auth_status(*, env: dict[str, str] | None = None, timeout: float = 45.0) -> dict[str, Any]:
    """Which credential the CLI is configured with — cheap, no API call.

    Careful with what this proves: `claude auth status` reports CONFIGURATION,
    not validity. A revoked or expired token still comes back
    `loggedIn: true, authMethod: "oauth_token"` (verified against the bundled
    CLI 2.1.139). To know whether the credential still WORKS you need
    `verify_credentials`, which makes a real round trip.

    What it does prove, and what nothing else in Rugol exposed before: which
    credential the CLI picked. Measured precedence on 2.1.139: an env
    CLAUDE_CODE_OAUTH_TOKEN is reported over a stored login, while a stored
    login is reported over an env ANTHROPIC_API_KEY. Having two configured at
    once is not fatal — the CLI can still fall back to the working one — but it
    makes every diagnosis ambiguous, which is why `rugol login` leaves exactly
    one behind.

    Never raises: on any failure the returned dict has `logged_in: False` and a
    human-readable `error`, because this feeds a health endpoint that must stay
    up precisely when auth is broken.
    """
    cli_path, source = find_cli()
    result: dict[str, Any] = {
        "cli_path": cli_path,
        "cli_source": source,
        "cli_version": "",
        "logged_in": False,
        "method": "",
        "provider": "",
        "account": "",
        "organization": "",
        "plan": "",
        "credential_source": "",
        "error": "",
        "checked_at": time.time(),
    }
    if not cli_path:
        result["error"] = (
            "No encontré el CLI de Claude. Reinstalá las dependencias del backend "
            "(`rugol update`) para recuperar el binario que trae claude-agent-sdk."
        )
        return result

    run_env = dict(env if env is not None else _run_env())
    # First guess at which credential Rugol is handing the CLI, from the env
    # alone; overwritten below by the CLI's own answer, which is authoritative.
    if run_env.get("ANTHROPIC_API_KEY"):
        result["credential_source"] = "api-key"
    elif run_env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        result["credential_source"] = "env-token"
    else:
        result["credential_source"] = "machine-login"

    result["cli_version"] = cli_version(cli_path)

    try:
        proc = subprocess.run(
            [cli_path, "auth", "status", "--json"],
            capture_output=True, text=True, timeout=timeout, env=run_env,
        )
    except subprocess.TimeoutExpired:
        result["error"] = f"`claude auth status` no respondió en {int(timeout)}s."
        return result
    except Exception as e:  # pragma: no cover — defensive
        result["error"] = f"No pude ejecutar el CLI de Claude: {e}"
        return result

    raw = (proc.stdout or "").strip()
    if not raw:
        result["error"] = (proc.stderr or "").strip() or "El CLI no devolvió nada."
        return result
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        result["error"] = f"Respuesta ilegible del CLI: {raw[:200]}"
        return result

    result["logged_in"] = bool(data.get("loggedIn"))
    result["method"] = str(data.get("authMethod") or "")
    # The CLI is the authority on which credential won; our env-based guess is
    # only the fallback for methods we don't recognise.
    method_to_source = {
        "oauth_token": "env-token",
        "api_key": "api-key",
        "claude.ai": "machine-login",
        "none": "none",
    }
    if result["method"] in method_to_source:
        result["credential_source"] = method_to_source[result["method"]]
    result["provider"] = str(data.get("apiProvider") or "")
    result["account"] = str(data.get("email") or "")
    result["organization"] = str(data.get("orgName") or "")
    result["plan"] = str(data.get("subscriptionType") or "")
    if not result["logged_in"] and not result["error"]:
        result["error"] = "La cuenta de Claude no está conectada en esta máquina."
    return result


def auth_status_cached(*, refresh: bool = False) -> dict[str, Any]:
    """`auth_status` behind a short TTL — the dashboard polls, the CLI spawn is ~1s."""
    global _cached_status
    now = time.monotonic()
    if not refresh and _cached_status and (now - _cached_status[0]) < _STATUS_TTL_SECONDS:
        return _cached_status[1]
    status = auth_status()
    _cached_status = (now, status)
    return status


def invalidate_cache() -> None:
    global _cached_status
    _cached_status = None


def env_file_path() -> Path:
    """Where the CLI wizard writes config: $RUGOL_HOME/.env, else the repo's .env."""
    if home := os.environ.get("RUGOL_HOME"):
        return Path(home) / ".env"
    from core.config import REPO_ROOT
    return REPO_ROOT / ".env"


def verify_credentials(*, env: dict[str, str] | None = None, timeout: float = 120.0) -> dict[str, Any]:
    """Does the credential actually work? One real, minimal round trip.

    There is no cheaper honest answer: `auth status` only reports what is
    configured, so a revoked token passes it. This asks Haiku for one word with
    the tools disabled and the system prompt replaced — a few tokens, ~2s — and
    reports the API's verdict, including the HTTP status when it refuses.

    Costs a fraction of a cent and consumes plan quota, so it runs only when
    someone asks for it (`rugol doctor`, `rugol login`, the dashboard button),
    never on a poll.
    """
    from core.llm_models import HAIKU

    out: dict[str, Any] = {"verified": False, "verify_error": "", "verify_status": None}
    cli_path, _ = find_cli()
    if not cli_path:
        out["verify_error"] = "No encontré el CLI de Claude."
        return out

    cmd = [
        cli_path, "-p", "ping",
        "--model", HAIKU,
        "--output-format", "json",
        "--tools", "",
        "--no-session-persistence",
        "--system-prompt", "Reply with the single word: ok",
        "--max-budget-usd", "0.05",
        "--setting-sources", "user",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=dict(env if env is not None else _run_env()),
        )
    except subprocess.TimeoutExpired:
        out["verify_error"] = f"La verificación no respondió en {int(timeout)}s."
        return out
    except Exception as e:  # pragma: no cover — defensive
        out["verify_error"] = f"No pude ejecutar el CLI de Claude: {e}"
        return out

    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}

    if not data:
        out["verify_error"] = (proc.stderr or "").strip() or "El CLI no devolvió nada."
        return out

    # `is_error` con `subtype: success` es el caso raro pero real: la corrida
    # terminó y el error viene del API, no del CLI.
    if data.get("is_error"):
        out["verify_status"] = data.get("api_error_status")
        out["verify_error"] = str(data.get("result") or "El API rechazó la credencial.")
        return out

    out["verified"] = True
    return out
