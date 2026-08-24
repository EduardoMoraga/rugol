"""FastAPI app entrypoint.

Run with: `uvicorn core.main:app --reload`
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import __version__
from core.adapters.slack import SlackAdapter
from core.adapters.telegram import TelegramAdapter
from core.api import (
    admin,
    agents,
    architect,
    channels,
    config_assistant,
    cv_sources,
    evolution,
    health,
    improvements,
    mcp_endpoint,
    memories,
    memory_graph,
    ontology,
    pipeline,
    projects,
    runs,
    schedules,
    skills,
    stream,
    templates,
    voice,
)
from core.api import settings as settings_api
from core.config import (
    adopt_legacy_data,
    adopt_legacy_state_dirs,
    data_dir,
    get_settings,
)
from core.db import init_db
from core.logging_setup import setup_logging
from core.maintenance import note_startup_backup
from core.registry.service import build_watcher, initial_scan
from core.resilience import set_last_report, startup_recovery
from core.scheduler import get_scheduler

# Consola + archivo rotativo. La redirección de la shell sigue capturando lo
# que pasa antes de esto (un traceback de importación); el log de la aplicación
# lo maneja Python, que es el único que puede rotarlo sin depender del arranque.
_LOG_FILE = setup_logging(logging.INFO)
logger = logging.getLogger(__name__)
if _LOG_FILE:
    logger.info("log de aplicación: %s", _LOG_FILE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Rugol core %s starting (subscription=%s)", __version__, settings.USE_SUBSCRIPTION)

    # 0. State location. Older versions kept settings.json and the scheduler
    # jobstore next to the CODE, so reinstalling wiped your schedules and your
    # dashboard-saved tokens. They live in RUGOL_DATA_DIR now; adopt whatever
    # the old location still holds, once, before anything reads it.
    adopted = adopt_legacy_data() + adopt_legacy_state_dirs()
    if adopted:
        logger.info("estado migrado a %s: %s", data_dir(), ", ".join(adopted))

    # 1. Database
    await init_db()

    # 1b. Recuperación de arranque (core/resilience): respaldo rotativo,
    # chequeo de integridad, y cierre de lo que quedó a mitad de camino. Va
    # ANTES del scheduler y de los adaptadores: si se corta la luz en medio de
    # una corrida, esas filas quedan en "running" para siempre y la vista de
    # flota miente hasta la próxima corrida de cada agente.
    recovery = await startup_recovery()
    set_last_report(recovery)

    # 2. Initial scan + watcher
    await initial_scan()
    watcher = build_watcher()
    watcher.start(asyncio.get_running_loop())

    # 3. Scheduler
    scheduler = get_scheduler()
    scheduler.start()

    # Mantenimiento horario. startup_recovery ya respaldó, así que el contador
    # arranca marcado para no duplicar el respaldo en la primera hora.
    note_startup_backup()
    scheduler.add_maintenance_job(hours=1)

    # 3b. Voice interviews — job de sync cada 5 min SOLO si ElevenLabs está
    # configurado. Idempotente; nunca fatal (no debe tumbar el backend).
    if settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_AGENT_ID:
        try:
            scheduler.add_voice_sync_job(interval_minutes=5)
        except Exception:
            logger.exception("no se pudo programar el voice sync job — continúo sin él")

    # 4. Adapters — NEVER fatal: if a chat platform is misconfigured or
    # unreachable, the rest of Rugol must keep working. We caught a
    # production bug where a Telegram getMe timeout brought the entire
    # backend down.
    telegram = TelegramAdapter()
    slack = SlackAdapter()
    try:
        await telegram.start()
    except Exception:
        logger.exception("telegram adapter failed to start — continuing without it")
    try:
        await slack.start()
    except Exception:
        logger.exception("slack adapter failed to start — continuing without it")

    app.state.watcher = watcher
    app.state.scheduler = scheduler
    app.state.telegram = telegram
    app.state.slack = slack

    yield

    # Shutdown
    logger.info("Rugol shutting down")
    await telegram.stop()
    await slack.stop()
    scheduler.shutdown()
    watcher.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rugol Core",
        version=__version__,
        description="Open-source operations center for Claude Code agents.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(templates.router, prefix="/api")
    app.include_router(channels.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(schedules.router, prefix="/api")
    app.include_router(ontology.router, prefix="/api")
    app.include_router(improvements.router, prefix="/api")
    app.include_router(settings_api.router, prefix="/api")
    app.include_router(architect.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    app.include_router(stream.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(config_assistant.router, prefix="/api")
    app.include_router(memories.router, prefix="/api")
    app.include_router(memory_graph.router, prefix="/api")
    app.include_router(pipeline.router, prefix="/api")
    app.include_router(evolution.router, prefix="/api")
    app.include_router(voice.router, prefix="/api")
    app.include_router(cv_sources.router, prefix="/api")

    # MCP sobre HTTP — la memoria como servicio, para los dos motores. Va SIN
    # el prefijo /api: es un endpoint de protocolo, no del API del dashboard, y
    # la URL viaja tal cual en la config de cada CLI.
    app.include_router(mcp_endpoint.router)

    # Capture the app for the agent runtime's endpoint inventory (so agents
    # see the exact list of REST paths and don't hallucinate new ones).
    from core.runner.api_inventory import set_app
    set_app(app)

    return app


app = create_app()
