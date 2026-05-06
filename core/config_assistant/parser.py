"""Parses arbitrary user input into a list of structured config actions.

Uses claude-agent-sdk under the hood — same auth path as the Architect.

Action shapes
-------------
Each action is a dict with `type`, an `id`, a human `description`, and
type-specific fields. The frontend renders them as checkboxes and the
user picks which to apply.

Supported types (v0.6 first cut):

- `set_telegram_token`    {token, allowed_users?}
- `set_slack_tokens`      {bot_token, app_token, signing_secret?}
- `add_mcp`               {agent_name, mcp_name, preset_id, env: {...}}

Future types can be added without breaking existing UI: unknown types are
shown as "no soportado" and not applied.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from core import runtime_state
from core.config import get_settings
from core.db import async_session_factory
from core.db.models import Agent, Project
from core.registry.service import upsert_agent_file

logger = logging.getLogger(__name__)


META_PROMPT = """Eres el Config Assistant de Rogologo. Recibís un fragmento de input del usuario (JSON, .env, texto con credenciales, output de otra herramienta) y devolvés un plan estructurado de acciones que Rogologo puede ejecutar.

INPUT_DEL_USUARIO:
{user_input}

CONTEXTO_DE_AGENTES_EXISTENTES:
{agent_context}

Reglas para el plan:
- Devolvé SIEMPRE un único objeto JSON, nada más. Sin texto antes ni después. Puede estar wrapeado en ```json o no.
- El JSON tiene UN campo: `actions` — array de objetos.
- Cada acción tiene `type`, `id` (string corto único en este plan), `description` (1 línea humana en español chileno) y campos según tipo.
- TIPOS DE ACCIÓN SOPORTADOS (otros se ignoran):
  * `set_telegram_token` — campos: `token` (string), `allowed_users` (string, opcional, ids comma-separated)
  * `set_slack_tokens` — campos: `bot_token`, `app_token`, `signing_secret` (todos opcionales individualmente)
  * `add_mcp` — campos: `agent_name` (debe ser uno de los agentes existentes), `mcp_name` (corto, lowercase, ej `notion`), `preset_id` (uno de: `notion`, `asana`, `github`, `brave-search`, `filesystem`, `gmail`, `google-calendar`), `env` (dict de KEY: value)
  * `setup_google_oauth_credentials` — campos: `credentials_json` (string, el JSON entero de credentials.json desde Google Cloud Console — incluye `installed.client_id` y `installed.client_secret`), `target_path` (opcional, default es `~/.gmail-mcp/gcp-oauth.keys.json`)
  * `set_google_api_key` — campos: `key` (string, API key tipo `AIzaSy...`)
- Si el input contiene OAuth client de Google (objeto `installed.client_id` + `installed.client_secret`), generá `setup_google_oauth_credentials` con el JSON entero. Esto es independiente de si después agregás `add_mcp` con preset `gmail` o `google-calendar` — la credential file tiene que existir antes de que cualquier MCP de Google funcione.
- Si el input contiene UNA Google API Key (string `AIzaSy...`), generá `set_google_api_key` (la usaremos para el MCP custom de YouTube cuando exista; por ahora la persistimos para que esté lista).
- IMPORTANTE: NO devuelvas tokens en la `description`. La description debe decir "configurar X con token de Y" SIN mostrar el valor.
- Si el input contiene varios bots Telegram (caso OpenClaw), recordá que Rogologo solo soporta UN bot Telegram a la vez. Elegí el más representativo (gugol o el del workspace) y describí qué descartaste.
- Si el input contiene MCP servers para múltiples agentes, generá una `add_mcp` por par (agente, mcp).
- Si el input no contiene nada accionable, devolvé `actions: []`.
- Si tenés dudas (ej: "no sé si este token es de Slack o de algo más"), NO lo metas en actions; mejor agregá un campo `unsure` array con strings explicando qué viste y no clasificaste.

Schema esperado:

{{
  "actions": [
    {{ "type": "set_telegram_token", "id": "tg-1", "description": "...", "token": "...", "allowed_users": "..." }},
    {{ "type": "set_slack_tokens", "id": "sl-1", "description": "...", "bot_token": "...", "app_token": "...", "signing_secret": "..." }},
    {{ "type": "add_mcp", "id": "mcp-1", "description": "...", "agent_name": "gugol", "mcp_name": "notion", "preset_id": "notion", "env": {{ "NOTION_TOKEN": "..." }} }},
    {{ "type": "setup_google_oauth_credentials", "id": "g-1", "description": "...", "credentials_json": "{{\\"installed\\": {{...}}}}", "target_path": null }},
    {{ "type": "set_google_api_key", "id": "g-2", "description": "...", "key": "AIzaSy..." }}
  ],
  "unsure": ["..."]
}}

Devolvé el JSON ahora. Sin saludos, sin comentarios."""


@dataclass
class ConfigAction:
    type: str
    id: str
    description: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_public_dict(self) -> dict[str, Any]:
        """Public-facing representation — DOES NOT include secret values."""
        masked: dict[str, Any] = {}
        for k, v in self.payload.items():
            if isinstance(v, str) and _looks_like_secret(k):
                masked[k] = _mask(v)
            elif isinstance(v, dict):
                # env dict — mask each value.
                masked[k] = {ek: _mask(ev) if isinstance(ev, str) else ev for ek, ev in v.items()}
            else:
                masked[k] = v
        return {
            "type": self.type,
            "id": self.id,
            "description": self.description,
            **masked,
        }


@dataclass
class ConfigPlan:
    actions: list[ConfigAction] = field(default_factory=list)
    unsure: list[str] = field(default_factory=list)
    raw_response: str = ""

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "actions": [a.as_public_dict() for a in self.actions],
            "unsure": self.unsure,
        }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


_SECRET_KEY_HINTS = ("token", "key", "secret", "password", "pass", "apikey")


def _looks_like_secret(key: str) -> bool:
    k = key.lower()
    return any(h in k for h in _SECRET_KEY_HINTS)


def _mask(value: str) -> str:
    if not value or not isinstance(value, str):
        return value
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _strip_outer_fence(text: str) -> str:
    if not text.startswith("```"):
        return ""
    nl = text.find("\n")
    if nl == -1:
        return ""
    inner = text[nl + 1 :]
    end = inner.rfind("```")
    return inner[:end] if end != -1 else inner


def _extract_json(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("empty response from config-assistant")
    stripped = text.strip()
    fence_inner = _strip_outer_fence(stripped)
    haystack = fence_inner if fence_inner and "{" in fence_inner else stripped
    obj_start = haystack.find("{")
    if obj_start == -1:
        raise ValueError("no JSON object found in config-assistant response")
    # Find matching closing brace
    depth = 0
    for i in range(obj_start, len(haystack)):
        c = haystack[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = haystack[obj_start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    candidate2 = re.sub(r",(\s*[}\]])", r"\1", candidate)
                    return json.loads(candidate2)
    raise ValueError("unbalanced JSON in config-assistant response")


PARSE_TIMEOUT_S = 60


async def parse_user_input(user_input: str) -> ConfigPlan:
    """Send the user input through claude-agent-sdk + meta-prompt, return a plan."""
    if len(user_input) > 12000:
        # Hard cap so we don't blow the model context with a 1MB paste.
        user_input = user_input[:12000] + "\n\n[...truncado...]"

    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as e:
        raise RuntimeError("claude-agent-sdk not installed") from e

    settings = get_settings()
    env = dict(os.environ)
    if settings.USE_SUBSCRIPTION:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    elif settings.ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY

    workspace = Path(__file__).resolve().parent.parent.parent

    options = ClaudeAgentOptions(
        cwd=str(workspace),
        model="claude-sonnet-4-6",
        permission_mode="bypassPermissions",
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": "You are the Rogologo Config Assistant. Output only the JSON object specified. Do not call tools, do not write files.",
        },
        setting_sources=["user"],
        env=env,
    )

    # Build agent context — the model needs to know which agents exist.
    async with async_session_factory() as session:
        agents = (await session.execute(select(Agent).order_by(Agent.name))).scalars().all()
    agent_context = (
        "\n".join(f"- {a.name} ({a.description[:80]})" for a in agents)
        or "(no hay agentes registrados)"
    )

    full_prompt = META_PROMPT.format(
        user_input=user_input.strip(),
        agent_context=agent_context,
    )

    parts: list[str] = []

    async def _drain() -> None:
        async for message in query(prompt=full_prompt, options=options):
            kind = type(message).__name__
            if kind == "AssistantMessage":
                for block in getattr(message, "content", []) or []:
                    btype = getattr(block, "type", None) or type(block).__name__.lower()
                    if btype in {"text", "textblock"}:
                        parts.append(getattr(block, "text", "") or "")
            elif kind == "ResultMessage":
                result = getattr(message, "result", None)
                if result and not parts:
                    parts.append(str(result))

    try:
        await asyncio.wait_for(_drain(), timeout=PARSE_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise ValueError(
            f"El Config Assistant no respondió en {PARSE_TIMEOUT_S}s. Probá con un input más corto."
        )

    raw = "".join(parts).strip()
    if not raw:
        raise ValueError(
            "El Config Assistant no devolvió texto. Verificá que `claude /login` esté configurado."
        )

    data = _extract_json(raw)
    plan = ConfigPlan(raw_response=raw)
    for raw_action in data.get("actions", []) or []:
        if not isinstance(raw_action, dict):
            continue
        action_type = str(raw_action.get("type", "")).strip()
        action_id = str(raw_action.get("id", "")).strip() or f"act-{len(plan.actions) + 1}"
        description = str(raw_action.get("description", "")).strip()
        payload = {
            k: v
            for k, v in raw_action.items()
            if k not in {"type", "id", "description"}
        }
        plan.actions.append(
            ConfigAction(
                type=action_type, id=action_id, description=description, payload=payload
            )
        )
    plan.unsure = [str(s) for s in data.get("unsure", []) if isinstance(s, str)]
    return plan


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


async def apply_plan(plan: ConfigPlan, selected_action_ids: set[str]) -> dict[str, Any]:
    """Apply only the actions whose ids are in selected_action_ids. Returns per-action results."""
    results: list[dict[str, Any]] = []
    for action in plan.actions:
        if action.id not in selected_action_ids:
            continue
        try:
            outcome = await _apply_one(action)
            results.append({"id": action.id, "ok": True, "outcome": outcome})
        except Exception as e:
            logger.exception("apply_plan failed for %s", action.id)
            results.append({"id": action.id, "ok": False, "error": str(e)})
    return {"results": results}


async def _apply_one(action: ConfigAction) -> str:
    if action.type == "set_telegram_token":
        token = str(action.payload.get("token", "")).strip()
        if not token:
            raise ValueError("missing token")
        runtime_state.save({"telegram_bot_token": token})
        allowed = action.payload.get("allowed_users")
        if allowed:
            runtime_state.save({"telegram_allowed_users": str(allowed).strip()})
        return "telegram bot token saved (restart adapter to apply)"

    if action.type == "set_slack_tokens":
        updates: dict[str, str] = {}
        for src, dst in (
            ("bot_token", "slack_bot_token"),
            ("app_token", "slack_app_token"),
            ("signing_secret", "slack_signing_secret"),
        ):
            v = action.payload.get(src)
            if v:
                updates[dst] = str(v).strip()
        if not updates:
            raise ValueError("no slack tokens provided")
        runtime_state.save(updates)
        return f"slack tokens saved: {', '.join(updates.keys())}"

    if action.type == "add_mcp":
        from core.adapters.telegram_wizards import find_preset, _patch_agent_mcp

        preset_id = str(action.payload.get("preset_id", "")).strip()
        agent_name = str(action.payload.get("agent_name", "")).strip()
        mcp_name = str(action.payload.get("mcp_name", "")).strip() or preset_id
        env = action.payload.get("env") or {}
        preset = find_preset(preset_id)
        if not preset:
            raise ValueError(f"preset desconocido: {preset_id}")
        async with async_session_factory() as session:
            a = (
                await session.execute(select(Agent).where(Agent.name == agent_name))
            ).scalar_one_or_none()
            if a is None:
                raise ValueError(f"agente no encontrado: {agent_name}")
            agent_id = a.id
        cfg = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", preset.package, *preset.extra_args],
            **({"env": env} if env else {}),
        }
        await _patch_agent_mcp(agent_id, mcp_name, cfg)
        return f"MCP {mcp_name} agregado al agente {agent_name}"

    if action.type == "setup_google_oauth_credentials":
        creds_raw = str(action.payload.get("credentials_json", "")).strip()
        if not creds_raw:
            raise ValueError("missing credentials_json")
        # Validate it parses
        try:
            parsed = json.loads(creds_raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"credentials_json no es JSON válido: {e}")
        # Sanity check: must be a Google OAuth installed-app credentials object
        if not isinstance(parsed, dict) or not (
            "installed" in parsed or "web" in parsed
        ):
            raise ValueError(
                "El JSON no parece un credentials.json de Google OAuth "
                "(falta `installed` o `web` en el root)."
            )
        target_raw = action.payload.get("target_path")
        target = (
            str(target_raw).strip()
            if target_raw
            else str(Path.home() / ".gmail-mcp" / "gcp-oauth.keys.json")
        )
        target_path = Path(target).expanduser()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(creds_raw, encoding="utf-8")
        return (
            f"Google OAuth credentials guardadas en `{target_path}`. "
            f"Próximo paso (manual, una sola vez): correr "
            f"`npx -y @gongrzhe/server-gmail-autoauth-mcp auth` para autorizar "
            f"el flujo OAuth en el browser."
        )

    if action.type == "set_google_api_key":
        key = str(action.payload.get("key", "")).strip()
        if not key:
            raise ValueError("missing key")
        # Persist under the workspace's data dir so it survives restarts and
        # is reachable by future MCP customs (YouTube etc).
        from core.config import get_settings

        settings = get_settings()
        # data/ is gitignored (see .gitignore)
        target = (
            Path(__file__).resolve().parent.parent.parent
            / "data"
            / "secrets"
            / "google-api-key.txt"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(key, encoding="utf-8")
        return (
            f"Google API key guardada en `{target}`. Va a usarse cuando "
            f"agreguemos el MCP custom de YouTube en una versión próxima."
        )

    raise ValueError(f"unsupported action type: {action.type}")
