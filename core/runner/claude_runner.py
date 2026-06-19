"""Wraps `claude-agent-sdk` subprocess execution.

Streams messages out via the bus while the run is alive. Returns final
result + token usage when ResultMessage is received.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

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
    """Shape the subprocess env for the chosen auth mode (ADR-002).

    Subscription mode: drop API-key vars and inject the long-lived
    CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) when present, so the
    bundled `claude` CLI authenticates headlessly — works in Docker and CI.
    API-key mode: set ANTHROPIC_API_KEY and strip any subscription token so
    the two never collide.
    """
    settings = get_settings()
    env = dict(os.environ)
    if settings.USE_SUBSCRIPTION:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        if settings.CLAUDE_CODE_OAUTH_TOKEN:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = settings.CLAUDE_CODE_OAUTH_TOKEN
    elif settings.ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


SYSTEM_PROMPT_APPEND = """You are running inside Rugol, a local agent operations platform.

# Output channel
- Your output is rendered both in a web dashboard and (optionally) sent to Telegram/Slack.
- Keep markdown clean; avoid huge tables when the channel is Telegram.
- If you generate files, save them to the workspace and mention paths.
- You may invoke subagents and skills as usual.

# CRITICAL — runtime state is NOT in files
The user can ask you two very different kinds of questions, and the answer source is different for each. Do not confuse them.

(A) Questions about RUGOL ITSELF — schedules, runs, agents, projects, settings, ontology.
- This data lives ONLY in Rugol's SQLite database. You CANNOT see it by reading files. Files in the filesystem with names like "schedule.py" or "morning_briefing" are scripts of UNRELATED projects belonging to the same user, NOT Rugol's runtime state.
- The ONLY correct way to answer these questions is via Rugol's REST API at the Rugol local API (exact base URL given below under "API base"). Use Bash + curl:
    GET /api/schedules              → list schedules
    GET /api/agents                 → list agents
    GET /api/agents/<id>/source     → agent body + mcp config
    GET /api/projects/<slug>        → project + lessons
    GET /api/settings               → telegram/slack token status
    GET /api/runs?limit=10          → recent runs
- If the API is unreachable for any reason, SAY SO explicitly: "no pude consultar /api/schedules (motivo: ...)". NEVER fabricate a list to fill the gap. NEVER infer schedule names from common patterns (e.g. "Morning Briefing", "Daily Report"). NEVER mix in real company names you know from training data (e.g. "SKF", "Versuni") to make a list look credible.
- Past failure modes this rule explicitly prevents:
    * Reading C:\\...\\some-other-project.py and reporting its hardcoded list as if it were Rugol's live state.
    * Confabulating a list of schedules with plausible names ("Lucy Morning Briefing", "SKF Daily Reports") when no API call was made.
    * Saying "let me verify" and then producing a confident-sounding table that was never actually verified against /api/schedules.
- Hard rule: if you did not just see a successful HTTP 2xx response from the API in this turn, you DO NOT KNOW the runtime state. Say "no tengo el dato y necesito que el backend esté corriendo en localhost:8000 para consultarlo".

(B) Questions about the USER's WORK — their workspace, clients, files, scripts, notes, anything in their PC.
- For these questions, exploring the filesystem is the WHOLE POINT of Rugol. Use Read/Bash/Glob/Grep freely against any path the user implicitly or explicitly references.
- Examples that are fully legitimate: "qué tareas tengo de Versuni esta semana" → grep their workspace; "abrí ese script de SKF" → Read directly; "hacé un dashboard con los datos de C:\\..." → use the path.
- The user gave the agent broad filesystem access deliberately so the agent can be useful across their actual work, not just Rugol's internal state.

The single rule: do not confuse the source. Internal state of Rugol → REST API only. Anything else → filesystem freely.
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
    telegram_mcp_server=None,
    telegram_tool_names: tuple[str, ...] = (),
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
    None falls back to a generic Rugol agent (no specific persona).
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
    #   2. SYSTEM_PROMPT_APPEND — Rugol platform rules
    #   3. endpoint inventory   — real /api/* paths the agent can call
    #   4. soul_context         — world state + identity + auto-memory (ADR-006)
    #   5. project_context      — project mission + lessons (ADR-005)
    from core.runner.api_inventory import render_endpoint_block

    parts: list[str] = []
    if agent_body and agent_body.strip():
        parts.append(
            "## Agent persona (your spec — what you are, how you work)\n"
            + agent_body.strip()
        )
    parts.append(SYSTEM_PROMPT_APPEND)
    endpoint_block = render_endpoint_block()
    if endpoint_block:
        parts.append(endpoint_block)
    # Base de API REAL (puerto dinámico en la app de escritorio empaquetada).
    _port = get_settings().CORE_PORT
    parts.append(
        f"## API base\nEl API local de Rugol corre en `http://127.0.0.1:{_port}`. "
        f"Úsalo para TODO curl al API (ej. `http://127.0.0.1:{_port}/api/...`). NUNCA uses otro puerto."
    )
    # Registro de actividad de dominio (solo variantes CRM/HRO): los agentes
    # anotan prospectos/candidatos en el pipeline para que el usuario los vea.
    _variant = os.environ.get("RUGOL_VARIANT", "rugol")
    if _variant in ("crm", "hro"):
        _kind = "lead" if _variant == "crm" else "candidate"
        _label = "prospecto" if _variant == "crm" else "candidato"
        parts.append(
            f"## Registrar actividad en el pipeline ({_label}s)\n"
            f"Cuando descubras, contactes, califiques o avances un {_label}, REGÍSTRALO vía el API para que "
            f"aparezca en el tablero del usuario (es la actividad que él quiere ver). Usa siempre `kind=\"{_kind}\"`.\n"
            f"- Crear: `curl -s -X POST http://127.0.0.1:{_port}/api/pipeline -H 'Content-Type: application/json' "
            f"-d '{{\"kind\":\"{_kind}\",\"title\":\"<empresa o nombre>\",\"subtitle\":\"<persona+cargo o rol>\","
            f"\"stage\":\"<etapa>\",\"score\":<1-5>,\"source_agent\":\"{agent_name}\",\"note\":\"<qué hiciste>\"}}'`\n"
            f"- Avanzar etapa / agregar nota: `curl -s -X PATCH http://127.0.0.1:{_port}/api/pipeline/<id> "
            f"-H 'Content-Type: application/json' -d '{{\"stage\":\"<nueva etapa>\",\"score\":<1-5>,"
            f"\"note\":\"<qué pasó>\",\"note_agent\":\"{agent_name}\"}}'`\n"
            f"- Ver el tablero: `GET /api/pipeline?kind={_kind}` · etapas válidas: `GET /api/pipeline/stages?kind={_kind}`.\n"
            f"No inventes datos de contacto: si no son públicos, anótalo en la nota."
        )
    if soul_context:
        parts.append(soul_context)
    if project_context:
        parts.append(project_context)
    system_append = "\n\n".join(parts)

    # `setting_sources=["user"]` — solo necesitamos el "user" setting source
    # para que la SDK use las credenciales de la subscripción Claude Pro/Max
    # autenticada en la máquina (~/.claude/). NO incluimos "project" ni
    # "local" porque eso haría que el agente lea el CLAUDE.md del repo de
    # Rugol y termine respondiendo como si fuera un dev del repo, en vez
    # de hablar como el agente que el usuario invocó. Bug encontrado al
    # probar un game-designer recién clonado: respondía sobre "Sprint 2 de
    # Rugol" en vez de sobre juegos educativos.
    options_kwargs: dict = dict(
        cwd=str(workspace_dir),
        model=model,
        permission_mode="bypassPermissions",
        system_prompt={"type": "preset", "preset": "claude_code", "append": system_append},
        resume=session_id,
        setting_sources=["user"],
        env=_build_env(),
    )
    # MCP servers merge order (v0.7.1 second fix — platform wins):
    #   - Per-agent configured servers come first.
    #   - Platform-provided servers (rugol-soul, rugol-telegram)
    #     overwrite ANY collision with their canonical name. This prevents
    #     a stale or wrong per-agent MCP config from silently breaking the
    #     in-process tools the runtime depends on.
    merged_mcp: dict = {}
    if mcp_servers:
        merged_mcp.update(mcp_servers)
    if soul_mcp_server is not None:
        merged_mcp["rugol-soul"] = soul_mcp_server
    if telegram_mcp_server is not None:
        merged_mcp["rugol-telegram"] = telegram_mcp_server

    # Built-in tools — preset (None) or agent whitelist (list).
    # CRITICAL: when the agent has a whitelist, MCP tools must be added
    # to that whitelist too. The CLI uses `--tools` as a "base set of
    # available tools" — anything not in there is invisible to the model,
    # no matter what allowed_tools says. allowed_tools is permissions,
    # tools is availability. The 2026-05-11 "Guardado" confabulation
    # incident with gugol was this: gugol has a tool whitelist, the
    # platform MCP tools were never in it, so the model never saw
    # save_memory existing — it just acknowledged like a polite assistant.
    platform_tool_names: list[str] = []
    for extra in list(soul_tool_names) + list(telegram_tool_names):
        if extra not in platform_tool_names:
            platform_tool_names.append(extra)

    if tools:
        tool_list = list(tools)
        for extra in platform_tool_names:
            if extra not in tool_list:
                tool_list.append(extra)
        options_kwargs["tools"] = tool_list
    # When tools is None/empty, we leave it unset so the CLI uses its
    # default preset, which surfaces MCP tools automatically. Confirmed
    # by the 2026-05-11 E2E test with company-analyst (tools=None).

    # `allowed_tools` is the SDK's auto-permit list. Used for the MCP
    # tools so they execute without permission prompts under
    # bypassPermissions mode.
    if platform_tool_names:
        options_kwargs["allowed_tools"] = list(platform_tool_names)

    if merged_mcp:
        options_kwargs["mcp_servers"] = merged_mcp
    options = ClaudeAgentOptions(**options_kwargs)

    parts: list[str] = []
    new_sid = session_id
    in_tok = out_tok = 0
    cost = 0.0

    try:
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
    except Exception as e:
        # El CLI a veces sale con código ≠ 0 DESPUÉS de haber producido una
        # respuesta válida: p.ej. "error result: success" (is_error=True con
        # subtype=success), o un cierre sucio de un MCP server / hook (más común
        # en Windows). Si ya tenemos texto del agente, entregamos la respuesta
        # en vez de fallar el run — un bot de chat debe contestar, no mostrar un
        # error críptico cuando en realidad respondió. Si NO hubo salida alguna,
        # es un fallo real y lo propagamos.
        if parts:
            logger.warning(
                "run %s (%s): query salió con error tras producir respuesta (%s); "
                "recupero el texto del agente",
                run_id, agent_name, e,
            )
        else:
            raise

    final_text = "".join(parts).strip() or "(run completed with no text output)"
    return RunResult(
        final_text=final_text,
        session_id=new_sid,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost,
    )
