"""Health and version endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from core import __version__
from core.runner.orchestrator import get_orchestrator

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "active_runs": get_orchestrator().active_count,
    }
