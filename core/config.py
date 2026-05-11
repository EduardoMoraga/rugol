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
    DEFAULT_MODEL: str = "claude-sonnet-4-6"  # core.llm_models.SONNET

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

    # Timezone for scheduling and world-state injection. Defaults to Chile;
    # any IANA name works (e.g. "America/Lima", "Europe/Madrid", "UTC").
    SCHEDULER_TIMEZONE: str = "America/Santiago"

    # Soul Layer — ADR-006/007/008
    # When true, every run hits the dispatcher classifier before model selection
    # (Soul-2). Disable to bypass the extra Haiku call (useful for benchmarks
    # or when running offline-ish without API credits).
    SOUL_DUAL_TRACK_ENABLED: bool = True
    SOUL_CLASSIFIER_MODEL: str = "claude-haiku-4-5-20251001"
    # When true and dispatcher returns S2, wrap the prompt to force a
    # plan-critique-answer structure (single round-trip). Off by default.
    SOUL_PLAN_THEN_EXECUTE_ENABLED: bool = False
    # When true, inject the agent's body (.md persona) into the system
    # prompt. v0.7.0-alpha shipped this ON and crashed the bundled CLI
    # subprocess for bodies >8 KB on Windows (command-line length limit).
    # v0.7.1 re-enables by default with a guard: if the body exceeds
    # SOUL_INJECT_BODY_MAX_CHARS, the orchestrator skips injection and
    # logs a warning instead of crashing. Soul-3 archive still works —
    # version bodies under the limit get injected, oversized ones are
    # noted in the run log.
    SOUL_INJECT_AGENT_BODY: bool = True
    SOUL_INJECT_BODY_MAX_CHARS: int = 8000
    # Soul-1.5 — after each completed run, fire a cheap Haiku evaluation
    # that decides whether to persist any durable memory from the
    # interaction. Without this, Soul-1's save_memory tool exists but is
    # rarely invoked (the model is focused on responding, not reflecting).
    # Default ON — adds ~$0.001-0.005 per primary run, but the memory
    # grows organically without the user having to type /remember.
    SOUL_AUTO_CHECKPOINT_ENABLED: bool = True
    # Skip the checkpoint when the primary run did NOT come from a real
    # conversation (e.g. schedule-fired, devil's advocate, reflection,
    # checkpoint of a checkpoint). The list below matches Run.source.
    SOUL_AUTO_CHECKPOINT_SKIP_SOURCES: str = "devils-advocate,schedule"
    # When true (and the agent has multiple active versions in its archive),
    # the runner routes runs across active versions per A/B (Soul-3). Off
    # by default — opt in once you have a proposer-driven branch.
    SOUL_EVOLUTION_AB_ENABLED: bool = False
    # Cadence multiplier for Soul-3 proposer. Higher = less frequent.
    # 1.0 = inherit existing trigger (every 10 runs or 3 consecutive fails).
    SOUL_PROPOSER_MULTIPLIER: float = 1.0

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
