"""Settings loaded from .env via pydantic-settings."""
from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core import llm_models

REPO_ROOT = Path(__file__).resolve().parent.parent


def data_dir_path() -> Path:
    """The resolved path, without touching the filesystem.

    Used where creating a directory would be a surprising import-time side
    effect (the DATABASE_URL default is evaluated when this module loads).
    """
    override = os.environ.get("RUGOL_DATA_DIR")
    return Path(override).expanduser() if override else REPO_ROOT / "data"


def data_dir() -> Path:
    """Where mutable state lives: the DB, the scheduler jobstore, settings.json.

    Defaults to `<repo>/data` so a bare checkout keeps working, but the CLI
    points `RUGOL_DATA_DIR` at `$RUGOL_HOME/data` — outside the app directory.
    That distinction is not cosmetic: reinstalling wipes the app directory, and
    schedules plus dashboard-saved tokens used to live inside it.
    """
    base = data_dir_path()
    base.mkdir(parents=True, exist_ok=True)
    return base


def state_dir(name: str) -> Path:
    """Carpetas de estado que NO son la base de datos: `agent-memory`,
    `agent-soul`.

    Vivían dentro del directorio de la app, que una reinstalación borra. Son el
    corazón del producto —lo que los agentes aprendieron y cómo evolucionaron
    sus prompts— guardado en el lugar más frágil de la instalación.
    """
    base = data_dir_path() / name
    base.mkdir(parents=True, exist_ok=True)
    return base


def adopt_legacy_state_dirs(names: tuple[str, ...] = ("agent-memory", "agent-soul")) -> list[str]:
    """Mueve las carpetas de estado que quedaron dentro del código.

    A diferencia de `adopt_legacy_data` (que copia archivos sueltos), acá
    copiamos árboles completos y sólo lo que falta en el destino, para no
    pisar nada que ya exista.
    """
    import shutil as _shutil

    if data_dir_path().resolve() == REPO_ROOT.resolve():
        return []
    adopted: list[str] = []
    for name in names:
        legacy = REPO_ROOT / name
        if not legacy.is_dir():
            continue
        target = data_dir_path() / name
        moved_any = False
        for child in legacy.iterdir():
            dest = target / child.name
            if dest.exists():
                continue
            target.mkdir(parents=True, exist_ok=True)
            try:
                if child.is_dir():
                    _shutil.copytree(child, dest)
                else:
                    _shutil.copy2(child, dest)
                moved_any = True
            except OSError:
                pass
        if moved_any:
            adopted.append(name)
    return adopted


def adopt_legacy_data(names: tuple[str, ...] = ("settings.json", "scheduler.db")) -> list[str]:
    """One-time pickup of state left behind in `<repo>/data` by older versions.

    Copies (never moves) so the old file stays as a backup, and only when the
    new location has nothing — an upgrade must not clobber current state.
    """
    legacy = REPO_ROOT / "data"
    if data_dir_path().resolve() == legacy.resolve():
        return []
    target = data_dir()
    adopted: list[str] = []
    for name in names:
        src, dst = legacy / name, target / name
        if src.is_file() and not dst.exists():
            try:
                shutil.copy2(src, dst)
                adopted.append(name)
            except OSError:
                pass
    return adopted


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
    # Long-lived subscription token from `claude setup-token` (Pro/Max).
    # Lets the bundled `claude` CLI authenticate headlessly — inside Docker
    # or CI — without the interactive login or the macOS Keychain. Used only
    # when USE_SUBSCRIPTION is true; ignored in API-key mode.
    CLAUDE_CODE_OAUTH_TOKEN: str = ""
    DEFAULT_MODEL: str = llm_models.SONNET

    # Codex (motor alternativo — core/runner/codex_runner).
    # Vacío = el CLI usa el login guardado en ~/.codex (`rugol login --codex`).
    OPENAI_API_KEY: str = ""
    # Sandbox de Codex: read-only | workspace-write | danger-full-access.
    # `workspace-write` escribe sólo en el directorio de trabajo y no tiene red.
    # Es el freno principal del motor Codex, así que subirlo es una decisión.
    CODEX_SANDBOX: str = "workspace-write"
    # Corte duro por corrida, en segundos. 0 = sin límite.
    CODEX_TIMEOUT_SECONDS: int = 900

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_USERS: str = ""
    # Multi-bot: a JSON list lets you run several bots at once, one per
    # project, each pinned to its own default agent. Example .env value:
    #   TELEGRAM_BOTS=[{"token":"123:abc","agent":"ventas","users":"42","label":"Ventas"}]
    # When empty, the single TELEGRAM_BOT_TOKEN above is used (back-compat).
    TELEGRAM_BOTS: list[dict] = []

    # Default agent — when a chat (e.g. Telegram) has no explicit binding,
    # messages auto-route to this agent so "token -> chat" works instantly,
    # Hermes-style. "assistant" → con solo pegar el token de Telegram el bot ya
    # responde (sin pedir User ID, sin /bind). Esa es la experiencia "Apple".
    DEFAULT_AGENT: str = "assistant"

    # Slack
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_APP_TOKEN: str = ""

    # ElevenLabs Conversational AI — entrevistas de voz "Sofía" (variante HRO).
    # Cuando ELEVENLABS_API_KEY está seteada, el módulo core.voice trae las
    # conversaciones reales del agente, las puntúa con BARS y las deja en el
    # pipeline de candidatos. Vacío → la integración de voz queda dormida.
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_AGENT_ID: str = ""

    # DB
    DATABASE_URL: str = f"sqlite+aiosqlite:///{data_dir_path() / 'rugol.db'}"

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
    SOUL_CLASSIFIER_MODEL: str = llm_models.HAIKU
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

    # Honcho — ADR-009 shared cross-agent memory.
    # Opt-in: when false (default), the honcho-ai SDK is never imported and
    # the rugol-honcho MCP server is not built. The Soul Layer keeps
    # working unchanged. Enable to give your agents a Plastic-Labs-backed
    # shared knowledge graph over external peers (users, clients).
    HONCHO_ENABLED: bool = False
    HONCHO_API_KEY: str = ""
    HONCHO_WORKSPACE_ID: str = "rugol-default"
    HONCHO_ENVIRONMENT: str = "production"
    # If empty, the adapter uses today's ISO date as session id, so
    # observations naturally group per day. Override for stable sessions.
    HONCHO_DEFAULT_SESSION: str = ""

    # Safety — frenos para el agente desatendido (core/safety).
    # Rugol corre con bypassPermissions y shell completa, en horarios, sin
    # nadie mirando. Estos denies son la única red que hay. Apagarlos es una
    # decisión consciente, no un default.
    SAFETY_GUARDS_ENABLED: bool = True
    # Regexes extra separadas por `;;` — se suman a las reglas de fábrica.
    # Ej: SAFETY_DENY_EXTRA=terraform\s+destroy;;kubectl\s+delete\s+ns
    SAFETY_DENY_EXTRA: str = ""
    # `freeze`: mientras esté seteado, los agentes sólo pueden escribir dentro
    # de esta carpeta. Vacío = sin restricción.
    SAFETY_FREEZE_DIR: str = ""

    # Security
    SESSION_SECRET: str = "change-me-to-a-random-32-char-string"

    @property
    def honcho_enabled(self) -> bool:
        return bool(self.HONCHO_ENABLED and self.HONCHO_API_KEY)

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
