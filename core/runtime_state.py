"""Mutable runtime settings — what the user changes from the dashboard.

Persisted as JSON under `data/settings.json`. The startup of `core.main`
reads this file and applies overrides on top of the static `Settings` from
`core.config`. POST `/api/settings` writes here and triggers a hot restart of
the affected subsystems (Telegram adapter, Slack adapter, registry watcher).
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.config import data_dir

logger = logging.getLogger(__name__)

# Resuelto en cada acceso, no al importar: el launcher setea RUGOL_DATA_DIR
# antes de arrancar y los tests lo mueven.
def settings_path() -> Path:
    return data_dir() / "settings.json"


@dataclass
class RuntimeSettings:
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""
    # Multi-bot: list of {token, agent, users, label}. When non-empty this
    # is the source of truth and the single token above is ignored.
    telegram_bots: list = field(default_factory=list)
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_app_token: str = ""
    agents_dir: str = ""  # absolute path; "" → fall back to config default
    skills_dir: str = ""
    default_model: str = ""
    # ElevenLabs (entrevistas de voz "Sofía"). Configurable desde el dashboard
    # para que cada usuario use SU propia cuenta (nada hardcodeado → shareable).
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    # HRO: fuentes de CV configurables (Pandapé, Chiletrabajo, Computrabajo,
    # LinkedIn, Drive, carpeta…). Cada una: {id, type, name, credentials, status}.
    # El connector las usa para traer candidatos al pipeline.
    cv_sources: list = field(default_factory=list)
    # Onboarding Instalar→Configurar→Enjoy: marca si el wizard ya se completó.
    onboarding_done: bool = False

    def as_public_dict(self) -> dict[str, Any]:
        """Mask secrets for the UI — return last 4 chars only."""
        def mask(v: str) -> str:
            return f"…{v[-4:]}" if v and len(v) > 6 else ""
        return {
            "telegram_bot_token_set": bool(self.telegram_bot_token),
            "telegram_bot_token_hint": mask(self.telegram_bot_token),
            "telegram_allowed_users": self.telegram_allowed_users,
            "telegram_bots": [
                {
                    "key": (str(b.get("token", "")).split(":", 1)[0] or "?"),
                    "agent": b.get("agent", ""),
                    "label": b.get("label", ""),
                    "token_hint": mask(str(b.get("token", ""))),
                }
                for b in (self.telegram_bots or [])
            ],
            "slack_bot_token_set": bool(self.slack_bot_token),
            "slack_bot_token_hint": mask(self.slack_bot_token),
            "slack_signing_secret_set": bool(self.slack_signing_secret),
            "slack_app_token_set": bool(self.slack_app_token),
            "slack_app_token_hint": mask(self.slack_app_token),
            "agents_dir": self.agents_dir,
            "skills_dir": self.skills_dir,
            "default_model": self.default_model,
            "elevenlabs_api_key_set": bool(self.elevenlabs_api_key),
            "elevenlabs_api_key_hint": mask(self.elevenlabs_api_key),
            "elevenlabs_agent_id": self.elevenlabs_agent_id,
            "cv_sources": [
                {
                    "id": str(s.get("id", "")),
                    "type": s.get("type", ""),
                    "name": s.get("name", ""),
                    "status": s.get("status", "configurada"),
                    "credentials_set": bool(s.get("credentials")),
                    "credentials_hint": mask(str(s.get("credentials", ""))),
                }
                for s in (self.cv_sources or [])
            ],
            "onboarding_done": bool(self.onboarding_done),
        }


_lock = threading.Lock()
_cached: RuntimeSettings | None = None


def load() -> RuntimeSettings:
    global _cached
    if _cached is not None:
        return _cached
    path = settings_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _cached = RuntimeSettings(**{k: v for k, v in data.items() if k in RuntimeSettings.__dataclass_fields__})
        except Exception:
            logger.exception("failed to read settings.json, using defaults")
            _cached = RuntimeSettings()
    else:
        _cached = RuntimeSettings()
    return _cached


def save(updates: dict[str, Any]) -> RuntimeSettings:
    """Merge updates into settings, persist to disk, return the new state."""
    global _cached
    with _lock:
        cur = load()
        merged = RuntimeSettings(
            **{**asdict(cur), **{k: v for k, v in updates.items() if k in RuntimeSettings.__dataclass_fields__}},
        )
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(merged), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        _cached = merged
    return merged


def telegram_token() -> str:
    s = load()
    return s.telegram_bot_token or ""


def telegram_allowed_user_ids() -> set[int]:
    raw = load().telegram_allowed_users
    if not raw:
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip().lstrip("-").isdigit()}


def _parse_user_set(raw: Any) -> set[int]:
    """Accept a comma-string, a list, or None → set of int user ids."""
    if raw is None:
        return set()
    items = raw if isinstance(raw, (list, set, tuple)) else str(raw).split(",")
    out: set[int] = set()
    for x in items:
        x = str(x).strip()
        if x.lstrip("-").isdigit():
            out.add(int(x))
    return out


def telegram_bots() -> list[dict]:
    """Normalized list of every configured Telegram bot.

    Source precedence:
      1. runtime_state.telegram_bots  (dashboard / multi-bot wizard)
      2. .env TELEGRAM_BOTS           (JSON list)
      3. legacy single bot: settings.json token, else .env TELEGRAM_BOT_TOKEN

    Each entry: {token, key, agent, users:set[int], label}. `key` is the
    bot's numeric id (token before ':') — unique per bot — used to namespace
    chat bindings/sessions so multiple bots never cross wires. Falling back
    to .env here is also what makes `rugol setup` (which writes .env) take
    effect without anyone touching the dashboard.
    """
    from core.config import get_settings
    s = load()
    cfg = get_settings()

    raw_list = list(s.telegram_bots or [])
    if not raw_list and getattr(cfg, "TELEGRAM_BOTS", None):
        raw_list = list(cfg.TELEGRAM_BOTS)
    if not raw_list:
        token = (s.telegram_bot_token or cfg.TELEGRAM_BOT_TOKEN or "").strip()
        if token:
            raw_list = [{
                "token": token,
                "agent": cfg.DEFAULT_AGENT,
                "users": s.telegram_allowed_users or cfg.TELEGRAM_ALLOWED_USERS,
                "label": "",
            }]

    out: list[dict] = []
    seen: set[str] = set()
    for b in raw_list:
        token = str(b.get("token") or "").strip()
        if not token or ":" not in token:
            continue
        key = token.split(":", 1)[0]
        if key in seen:
            continue  # same bot twice → would Conflict on polling
        seen.add(key)
        out.append({
            "token": token,
            "key": key,
            "agent": str(b.get("agent") or cfg.DEFAULT_AGENT or "").strip(),
            "users": _parse_user_set(b.get("users")),
            "label": str(b.get("label") or "").strip(),
        })
    return out


def slack_tokens() -> tuple[str, str, str]:
    s = load()
    return s.slack_bot_token, s.slack_signing_secret, s.slack_app_token


def elevenlabs_creds() -> tuple[str, str]:
    """(api_key, agent_id) para la voz de Sofía. Prioriza lo guardado desde el
    dashboard (settings.json); cae a env/.env (ELEVENLABS_*) si no hay."""
    s = load()
    from core.config import get_settings
    cfg = get_settings()
    return (
        (s.elevenlabs_api_key or cfg.ELEVENLABS_API_KEY or "").strip(),
        (s.elevenlabs_agent_id or cfg.ELEVENLABS_AGENT_ID or "").strip(),
    )


def agents_dir() -> Path:
    s = load()
    if s.agents_dir:
        return Path(s.agents_dir)
    from core.config import get_settings
    return get_settings().AGENTS_DIR


def skills_dir() -> Path:
    s = load()
    if s.skills_dir:
        return Path(s.skills_dir)
    from core.config import get_settings
    return get_settings().SKILLS_DIR


def default_model() -> str:
    s = load()
    if s.default_model:
        return s.default_model
    from core.config import get_settings
    return get_settings().DEFAULT_MODEL


def cv_sources_list() -> list[dict]:
    """Lista cruda de fuentes de CV (con credenciales, para el backend/connector).
    La UI consume la versión enmascarada de as_public_dict()."""
    return list(load().cv_sources or [])
