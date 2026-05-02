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

from core.config import REPO_ROOT

logger = logging.getLogger(__name__)

SETTINGS_PATH = REPO_ROOT / "data" / "settings.json"


@dataclass
class RuntimeSettings:
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_app_token: str = ""
    agents_dir: str = ""  # absolute path; "" → fall back to config default
    skills_dir: str = ""
    default_model: str = ""

    def as_public_dict(self) -> dict[str, Any]:
        """Mask secrets for the UI — return last 4 chars only."""
        def mask(v: str) -> str:
            return f"…{v[-4:]}" if v and len(v) > 6 else ""
        return {
            "telegram_bot_token_set": bool(self.telegram_bot_token),
            "telegram_bot_token_hint": mask(self.telegram_bot_token),
            "telegram_allowed_users": self.telegram_allowed_users,
            "slack_bot_token_set": bool(self.slack_bot_token),
            "slack_bot_token_hint": mask(self.slack_bot_token),
            "slack_signing_secret_set": bool(self.slack_signing_secret),
            "slack_app_token_set": bool(self.slack_app_token),
            "slack_app_token_hint": mask(self.slack_app_token),
            "agents_dir": self.agents_dir,
            "skills_dir": self.skills_dir,
            "default_model": self.default_model,
        }


_lock = threading.Lock()
_cached: RuntimeSettings | None = None


def load() -> RuntimeSettings:
    global _cached
    if _cached is not None:
        return _cached
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
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
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
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


def slack_tokens() -> tuple[str, str, str]:
    s = load()
    return s.slack_bot_token, s.slack_signing_secret, s.slack_app_token


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
