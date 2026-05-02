"""Settings loaded from .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM auth
    USE_SUBSCRIPTION: bool = True
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_MODEL: str = "claude-sonnet-4-6"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_USERS: str = ""

    # Slack
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_APP_TOKEN: str = ""

    # DB
    DATABASE_URL: str = f"sqlite+aiosqlite:///{REPO_ROOT / 'data' / 'rogologo.db'}"

    # Server
    CORE_HOST: str = "0.0.0.0"
    CORE_PORT: int = 8000

    # Discovery — defaults match the bundled templates so a fresh checkout finds agents.
    AGENTS_DIR: Path = Field(default=REPO_ROOT / "agents-templates")
    SKILLS_DIR: Path = Field(default=REPO_ROOT / "skills-templates")
    DISCOVERY_INTERVAL: int = 5

    # Concurrency
    MAX_CONCURRENT_RUNS: int = 3

    # UI hints
    DEFAULT_LANG: str = "en"
    ANT_FARM_ENABLED: bool = True

    # Telemetry
    TELEMETRY_ENABLED: bool = False

    # Security
    SESSION_SECRET: str = "change-me-to-a-random-32-char-string"

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN)

    @property
    def slack_enabled(self) -> bool:
        return bool(self.SLACK_BOT_TOKEN and self.SLACK_APP_TOKEN)

    @property
    def telegram_allowed_user_ids(self) -> set[int]:
        if not self.TELEGRAM_ALLOWED_USERS:
            return set()
        return {int(x.strip()) for x in self.TELEGRAM_ALLOWED_USERS.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
