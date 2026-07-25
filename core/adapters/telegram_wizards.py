"""Conversational wizards for the Telegram adapter.

Implements multi-step state machines that let the user configure MCP servers
and agents through a chat conversation, without ever touching the dashboard.

Why this exists
---------------
OpenClaw has a similar onboarding wizard that walks the user through setup
from inside Telegram. v0.5 of Rugol required jumping into the dashboard
for every config change — a hard ask for users who already operate from a
phone. The wizard closes that gap.

State is kept in-memory per chat_id. If the process restarts mid-wizard the
user just runs /cancel and starts over. We deliberately don't persist
secrets-in-flight: a token typed by the user gets applied to the agent's
mcp_servers and dropped from memory in the same step.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from core.db import async_session_factory
from core.db.models import Agent, Project
from core.mcp import test_mcp_server
from core.registry.service import upsert_agent_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Catalog of common MCP presets — same list the dashboard's MCP Catalog uses.
# Each preset declares everything we need to build the stdio config and to
# guide the user on where to obtain the token.
# ---------------------------------------------------------------------------


@dataclass
class McpPreset:
    id: str          # short slug used as the MCP server name on the agent
    label: str       # human label
    package: str     # npm package run via npx -y (or path for python presets)
    env_keys: list[str]  # env var names the user must paste
    token_help: str  # message shown when asking for the token
    extra_args: list[str] = field(default_factory=list)  # args appended after the package
    # When `is_python` is True, the build_mcp_config helper resolves command
    # to sys.executable and treats `package` as a path RELATIVE to the repo
    # root. Used by `youtube` (custom MCP shipped under scripts/mcp/).
    is_python: bool = False
    # Whether the wizard should ask for an extra arg (e.g. filesystem path).
    requires_extra_arg: bool = False


def build_mcp_config(preset: McpPreset, env: dict[str, str], extra_args: list[str] | None = None) -> dict[str, Any]:
    """Build the {type, command, args, env} dict that gets stored on the agent.

    Honors is_python: if True, command becomes the current Python interpreter
    and args is the absolute path to the script (under the repo root).
    Otherwise it's the standard `npx -y <package>` invocation.
    """
    import sys as _sys
    from pathlib import Path as _Path

    extras = list(extra_args or [])
    if preset.is_python:
        # `package` is a repo-relative path to a script.
        repo_root = _Path(__file__).resolve().parent.parent.parent
        script_path = (repo_root / preset.package).resolve()
        cfg: dict[str, Any] = {
            "type": "stdio",
            "command": _sys.executable,
            "args": [str(script_path), *preset.extra_args, *extras],
        }
    else:
        cfg = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", preset.package, *preset.extra_args, *extras],
        }
    if env:
        cfg["env"] = dict(env)
    return cfg


CATALOG: list[McpPreset] = [
    McpPreset(
        id="notion",
        label="Notion",
        package="@notionhq/notion-mcp-server",
        env_keys=["NOTION_TOKEN"],
        token_help=(
            "Para Notion necesito un Internal Integration Token.\n\n"
            "1. Andá a https://www.notion.so/profile/integrations\n"
            "2. Click *New integration* → ponele un nombre (ej: Rugol)\n"
            "3. Copiá el secret que empieza con `ntn_...`\n"
            "4. Vuelve y pégamelo aquí\n\n"
            "Después tienes que dar acceso a las páginas/databases que quieres "
            "que el agente vea (Notion → página → Add connections → tu integración)."
        ),
    ),
    McpPreset(
        id="asana",
        label="Asana",
        package="@cristip73/mcp-server-asana",
        env_keys=["ASANA_ACCESS_TOKEN"],
        token_help=(
            "Para Asana necesito un Personal Access Token.\n\n"
            "1. Andá a https://app.asana.com/0/my-apps\n"
            "2. Click *Create new token*\n"
            "3. Copiá el token (lo ves UNA SOLA VEZ)\n"
            "4. Pégamelo aquí"
        ),
    ),
    McpPreset(
        id="github",
        label="GitHub",
        package="@modelcontextprotocol/server-github",
        env_keys=["GITHUB_PERSONAL_ACCESS_TOKEN"],
        token_help=(
            "Para GitHub necesito un Personal Access Token (classic).\n\n"
            "1. Andá a https://github.com/settings/tokens\n"
            "2. Click *Generate new token (classic)*\n"
            "3. Marca los scopes que quieras (mínimo: `repo` y `read:org`)\n"
            "4. Copiá el token que empieza con `ghp_...`\n"
            "5. Pégamelo aquí"
        ),
    ),
    McpPreset(
        id="brave-search",
        label="Brave Search (web search)",
        package="@modelcontextprotocol/server-brave-search",
        env_keys=["BRAVE_API_KEY"],
        token_help=(
            "Para Brave Search necesito una API key.\n\n"
            "1. Andá a https://api.search.brave.com/app/keys\n"
            "2. Creá una API key (la free tier alcanza para uso personal)\n"
            "3. Pégamela aquí"
        ),
    ),
    McpPreset(
        id="filesystem",
        label="Filesystem (lectura de archivos locales)",
        package="@modelcontextprotocol/server-filesystem",
        env_keys=[],  # no token, but the path goes as an arg
        token_help=(
            "Filesystem no necesita token. Decime una RUTA absoluta que el "
            "agente pueda leer (ej: `C:\\Trabajo\\Proyectos`)."
        ),
        requires_extra_arg=True,
    ),
    McpPreset(
        id="gmail",
        label="Gmail (lectura + envío con OAuth)",
        package="@gongrzhe/server-gmail-autoauth-mcp",
        env_keys=[],  # uses credentials at ~/.gmail-mcp/gcp-oauth.keys.json
        token_help=(
            "Gmail usa OAuth completo. Antes de poder usarlo:\n\n"
            "1. Necesitás credentials.json desde Google Cloud Console "
            "(APIs & Services → Credentials → OAuth client ID, tipo *Desktop*).\n"
            "2. Lo más fácil: usa el *Asistente de configuración* del dashboard "
            "y pega el JSON entero — yo lo guardo donde el MCP lo busca.\n"
            "3. Después corré una sola vez:\n"
            "   `npx -y @gongrzhe/server-gmail-autoauth-mcp auth`\n"
            "   Eso abre el browser para que autorices.\n\n"
            "Para registrarlo aquí igual, escribe cualquier cosa o `/cancel` "
            "y configura desde el dashboard."
        ),
    ),
    McpPreset(
        id="google-calendar",
        label="Google Calendar (lectura + escritura con OAuth)",
        package="@cocal/google-calendar-mcp",
        env_keys=["GOOGLE_OAUTH_CREDENTIALS"],
        token_help=(
            "Google Calendar usa OAuth. Pasos:\n\n"
            "1. Pega el path absoluto de tu credentials.json. Ej: "
            "`C:\\Users\\<usuario>\\.gmail-mcp\\gcp-oauth.keys.json` (lo mismo "
            "que usas para Gmail).\n\n"
            "El MCP toma `GOOGLE_OAUTH_CREDENTIALS` como path al credentials. "
            "Después corré `npx @cocal/google-calendar-mcp` y autorizá la "
            "primera vez."
        ),
    ),
    McpPreset(
        id="youtube",
        label="YouTube Data API (custom Rugol, solo necesita API key)",
        package="scripts/mcp/youtube_server.py",  # repo-relative; build_mcp_config resolves
        env_keys=["YOUTUBE_API_KEY"],
        token_help=(
            "YouTube usa una API key (no OAuth). Si ya pegaste tu key vía "
            "/config-assistant, ya está guardada en `data/secrets/google-api-key.txt` "
            "y el MCP la lee automáticamente — escribime cualquier cosa para continuar.\n\n"
            "Si no, pega tu API key (formato `AIzaSy...`). Si no tienes, "
            "se crea en https://console.cloud.google.com/apis/credentials → "
            "*Create credentials → API key* → habilitá *YouTube Data API v3*."
        ),
        is_python=True,
    ),
    McpPreset(
        id="playwright",
        label="Playwright (scraping web + automatización de browser)",
        package="@playwright/mcp@latest",
        env_keys=[],
        token_help=(
            "Playwright MCP oficial de Microsoft. El agente puede:\n"
            "- Navegar URLs y extraer contenido (scraping)\n"
            "- Llenar formularios, hacer clicks, esperar elementos\n"
            "- Tomar screenshots\n"
            "- Trabajar con accessibility tree (más confiable que CSS selectors)\n\n"
            "Pre-requisito (una sola vez): instalar Chromium con\n"
            "    npx playwright install chromium\n\n"
            "Si la primera ejecución del agente da error 'browser not found', "
            "corré ese comando en PowerShell y reintentá."
        ),
    ),
]


def find_preset(preset_id: str) -> McpPreset | None:
    for p in CATALOG:
        if p.id == preset_id.lower().strip():
            return p
    return None


# ---------------------------------------------------------------------------
# Wizard state machines
# ---------------------------------------------------------------------------


@dataclass
class WizardState:
    kind: str  # "mcp" | "agent"
    step: str
    data: dict[str, Any] = field(default_factory=dict)


# In-memory store: chat_id (int) → WizardState
_WIZARDS: dict[int, WizardState] = {}


def is_in_wizard(chat_id: int) -> bool:
    return chat_id in _WIZARDS


def cancel_wizard(chat_id: int) -> bool:
    return _WIZARDS.pop(chat_id, None) is not None


# ---------------------------------------------------------------------------
# /setup_mcp wizard
# ---------------------------------------------------------------------------


async def start_setup_mcp(chat_id: int) -> str:
    """Start the wizard. Lists agents."""
    async with async_session_factory() as session:
        agents = (await session.execute(select(Agent).order_by(Agent.name))).scalars().all()
    if not agents:
        return "No hay agentes registrados todavía. Usa /setup_agent primero."
    _WIZARDS[chat_id] = WizardState(kind="mcp", step="pick_agent", data={})
    lines = "\n".join(f"• {a.name}" for a in agents)
    return (
        "Vamos a conectar un MCP a un agente.\n\n"
        "Paso 1/4 — ¿A qué agente?\n\n"
        f"Agentes disponibles:\n{lines}\n\n"
        "Escribe solo el nombre. Para abortar: /cancel."
    )


async def step_setup_mcp(chat_id: int, text: str) -> tuple[str, bool]:
    """Advance the /setup_mcp wizard. Returns (reply_text, finished).

    All strings here are plain text (no Markdown). Telegram's Markdown V1
    parser is fragile around underscores and brackets, and tool names like
    `search_videos` reliably break it. Plain text is uglier but never crashes.
    """
    state = _WIZARDS.get(chat_id)
    if not state or state.kind != "mcp":
        return ("(no hay un wizard activo)", True)
    text = text.strip()

    if state.step == "pick_agent":
        async with async_session_factory() as session:
            agent = (
                await session.execute(select(Agent).where(Agent.name == text))
            ).scalar_one_or_none()
        if agent is None:
            return (f"No existe el agente '{text}'. Escribe otro o /cancel.", False)
        state.data["agent_id"] = agent.id
        state.data["agent_name"] = agent.name
        state.step = "pick_preset"
        catalog_lines = "\n".join(f"• {p.id} — {p.label}" for p in CATALOG)
        return (
            f"Bien, agente '{agent.name}' seleccionado.\n\n"
            "Paso 2/4 — ¿Qué MCP?\n\n"
            f"Presets disponibles:\n{catalog_lines}\n\n"
            "Escribe el id (ej: notion). Para algo custom: /cancel y configura desde el dashboard.",
            False,
        )

    if state.step == "pick_preset":
        preset = find_preset(text)
        if preset is None:
            return (f"No conozco el preset '{text}'. Escribe otro o /cancel.", False)
        state.data["preset_id"] = preset.id
        if not preset.env_keys and not preset.requires_extra_arg:
            # Nothing to ask the user — finalize directly. Used by `youtube`,
            # which auto-resolves the API key from data/secrets.
            return await _finalize_mcp_install(chat_id, preset)
        if not preset.env_keys:
            # Filesystem-style: extra arg only.
            state.step = "collect_args"
            return (
                f"Paso 3/4 — Configuración de {preset.label}\n\n{_strip_md(preset.token_help)}",
                False,
            )
        state.step = "collect_env"
        state.data["env_remaining"] = list(preset.env_keys)
        state.data["env_collected"] = {}
        return (
            f"Paso 3/4 — Token para {preset.label}\n\n{_strip_md(preset.token_help)}",
            False,
        )

    if state.step == "collect_env":
        preset = find_preset(state.data["preset_id"])
        if preset is None:
            return ("Error interno: preset no encontrado.", True)
        remaining: list[str] = state.data["env_remaining"]
        collected: dict[str, str] = state.data["env_collected"]
        current_key = remaining.pop(0)
        collected[current_key] = text
        if remaining:
            return (
                f"Listo. Próximo: necesito el valor para {remaining[0]}.",
                False,
            )
        # All env collected → save and test.
        return await _finalize_mcp_install(chat_id, preset)

    if state.step == "collect_args":
        preset = find_preset(state.data["preset_id"])
        if preset is None:
            return ("Error interno: preset no encontrado.", True)
        # Use the typed text as the path argument (filesystem) or stash for the
        # call. We treat it as an extra arg appended after the package.
        state.data["extra_args"] = [text]
        return await _finalize_mcp_install(chat_id, preset)

    return ("(estado de wizard inesperado, abortando)", True)


async def _finalize_mcp_install(chat_id: int, preset: McpPreset) -> tuple[str, bool]:
    """Apply the MCP config to the agent, run the test, drop the wizard state."""
    state = _WIZARDS.get(chat_id)
    if not state:
        return ("(estado perdido)", True)
    agent_id: int = state.data["agent_id"]
    agent_name: str = state.data["agent_name"]
    env: dict[str, str] = state.data.get("env_collected", {})
    extra_args: list[str] = state.data.get("extra_args", [])

    cfg = build_mcp_config(preset, env, extra_args)

    # Persist on the agent's frontmatter.
    try:
        await _patch_agent_mcp(agent_id, preset.id, cfg)
    except Exception as e:
        logger.exception("could not patch agent mcp via wizard")
        cancel_wizard(chat_id)
        return (f"Error guardando la config: {e}", True)

    # Run the test endpoint logic directly so the user gets feedback in the chat.
    test_result = await test_mcp_server(
        command=cfg["command"], args=cfg["args"], env=cfg.get("env") or {}
    )
    cancel_wizard(chat_id)

    if test_result.ok:
        tools_preview = ", ".join(test_result.tools[:6]) or "(sin herramientas detectadas)"
        more = f" (+{len(test_result.tools) - 6} más)" if len(test_result.tools) > 6 else ""
        return (
            "Paso 4/4 — Test OK\n\n"
            f"{preset.label} quedó conectado a {agent_name} y respondió en {test_result.duration_ms} ms.\n\n"
            f"Herramientas detectadas: {tools_preview}{more}\n\n"
            "Listo para usar.",
            True,
        )
    err_brief = (test_result.error or "").splitlines()[0][:200]
    return (
        "Paso 4/4 — Test falló\n\n"
        f"La config quedó guardada en {agent_name} (puedes probarla después desde el dashboard), "
        "pero el handshake JSON-RPC no respondió.\n\n"
        f"Tipo de error: {test_result.error_kind or 'desconocido'}\n"
        f"Detalle: {err_brief}\n\n"
        "Próximo paso: revisá la config en el dashboard, o prueba con otro preset.",
        True,
    )


async def _patch_agent_mcp(agent_id: int, mcp_name: str, cfg: dict[str, Any]) -> None:
    """Merge a single MCP server into the agent's mcp_servers and persist via the .md file."""
    async with async_session_factory() as session:
        agent = await session.get(Agent, agent_id)
        if agent is None:
            raise RuntimeError(f"agent {agent_id} not found")
        existing = dict(agent.mcp_servers or {})
        existing[mcp_name] = cfg
        # Build the same frontmatter we'd write from the API.
        path = Path(agent.source_path)
        frontmatter_lines = ["---", f"name: {agent.name}", f"model: {agent.model}"]
        if agent.project_id:
            proj = await session.get(Project, agent.project_id)
            if proj:
                frontmatter_lines.append(f"project: {proj.slug}")
        if agent.tools:
            tool_csv = ", ".join(t.strip() for t in agent.tools if t.strip())
            if tool_csv:
                frontmatter_lines.append(f"tools: [{tool_csv}]")
        frontmatter_lines.append(
            f"mcp_servers: {json.dumps(existing, ensure_ascii=False)}"
        )
        esc = (agent.description or "").replace("\\", "\\\\").replace('"', '\\"')
        frontmatter_lines.append(f'description: "{esc}"')
        frontmatter_lines.append("---")
        body = (agent.body or "").strip() + "\n"
        full = "\n".join(frontmatter_lines) + "\n\n" + body

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(full, encoding="utf-8")
    await upsert_agent_file(path)


# ---------------------------------------------------------------------------
# /list_mcps — quick read-only
# ---------------------------------------------------------------------------


def _strip_md(text: str) -> str:
    """Drop Markdown formatting characters that would otherwise break Telegram's
    fragile MD V1 parser when interpolated into a wizard message."""
    return text.replace("`", "").replace("*", "").replace("_", " ")


async def list_mcps_for_chat() -> str:
    async with async_session_factory() as session:
        agents = (await session.execute(select(Agent).order_by(Agent.name))).scalars().all()
    if not agents:
        return "No hay agentes registrados."
    lines: list[str] = []
    for a in agents:
        mcps = a.mcp_servers or {}
        if not mcps:
            lines.append(f"• {a.name} — sin MCPs")
            continue
        names = ", ".join(mcps.keys())
        lines.append(f"• {a.name} → {names}")
    return "MCPs por agente:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# /test_mcp <agente> <mcp>
# ---------------------------------------------------------------------------


async def test_mcp_for_chat(args: list[str]) -> str:
    if len(args) < 2:
        return "Uso: /test_mcp <agente> <mcp>  — ej. /test_mcp gugol notion"
    agent_name = args[0].strip()
    mcp_name = args[1].strip()
    async with async_session_factory() as session:
        agent = (
            await session.execute(select(Agent).where(Agent.name == agent_name))
        ).scalar_one_or_none()
    if agent is None:
        return f"No existe el agente '{agent_name}'."
    mcps = agent.mcp_servers or {}
    cfg = mcps.get(mcp_name)
    if not cfg:
        return f"El agente '{agent_name}' no tiene un MCP llamado '{mcp_name}'."
    command = cfg.get("command")
    args_list = cfg.get("args") or []
    env = cfg.get("env") or {}
    if not command:
        return f"El MCP '{mcp_name}' no tiene command (probablemente es SSE/HTTP, no stdio). Por ahora solo testeo stdio."
    result = await test_mcp_server(command=command, args=args_list, env=env)
    if result.ok:
        tools = ", ".join(result.tools[:8]) or "(sin tools)"
        more = f" (+{len(result.tools) - 8} más)" if len(result.tools) > 8 else ""
        return (
            f"{agent_name} / {mcp_name} — OK ({result.duration_ms} ms)\n\n"
            f"Herramientas: {tools}{more}"
        )
    err_brief = (result.error or "").splitlines()[0][:200]
    return (
        f"{agent_name} / {mcp_name} — Falló\n\n"
        f"Tipo: {result.error_kind or 'desconocido'}\n"
        f"Detalle: {err_brief}"
    )
