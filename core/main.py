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
from core.api import agents, architect, health, improvements, ontology, projects, runs, schedules, settings as settings_api, skills, stream
from core.config import get_settings
from core.db import init_db
from core.registry.service import build_watcher, initial_scan
from core.scheduler import get_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Rogologo core %s starting (subscription=%s)", __version__, settings.USE_SUBSCRIPTION)

    # 1. Database
    await init_db()

    # 2. Initial scan + watcher
    await initial_scan()
    watcher = build_watcher()
    watcher.start(asyncio.get_running_loop())

    # 3. Scheduler
    scheduler = get_scheduler()
    scheduler.start()

    # 4. Adapters
    telegram = TelegramAdapter()
    slack = SlackAdapter()
    await telegram.start()
    await slack.start()

    app.state.watcher = watcher
    app.state.scheduler = scheduler
    app.state.telegram = telegram
    app.state.slack = slack

    yield

    # Shutdown
    logger.info("Rogologo shutting down")
    await telegram.stop()
    await slack.stop()
    scheduler.shutdown()
    watcher.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rogologo Core",
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
    app.include_router(agents.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(schedules.router, prefix="/api")
    app.include_router(ontology.router, prefix="/api")
    app.include_router(improvements.router, prefix="/api")
    app.include_router(settings_api.router, prefix="/api")
    app.include_router(architect.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    app.include_router(stream.router, prefix="/api")

    return app


app = create_app()
