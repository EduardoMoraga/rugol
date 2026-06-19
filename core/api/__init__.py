"""FastAPI routers grouped by resource."""
from . import agents, health, improvements, ontology, runs, schedules, stream, voice

__all__ = ["agents", "health", "improvements", "ontology", "runs", "schedules", "stream", "voice"]
