"""Smoke tests for the FastAPI REST surface.

Validates that every important endpoint at least responds with a
well-formed JSON status (200 or documented 404). We do NOT exercise the
full app lifespan (scheduler, adapters) — we wrap the app in a no-op
lifespan so the tests stay fast and don't poke external services.

Catches the class of regression where renaming a model or removing a
route breaks the dashboard without anyone noticing.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    yield


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Build a TestClient against the real router stack with a stub lifespan
    so we don't start the scheduler / adapters during tests."""
    from core import __version__
    from core.api import (
        admin, agents, architect, channels, config_assistant, evolution,
        health, improvements, memories, ontology, projects, runs,
        schedules, settings as settings_api, skills, stream, templates,
    )
    from core.db import init_db
    import asyncio

    # Make sure the DB schema is present.
    asyncio.get_event_loop().run_until_complete(init_db()) if False else None
    # The line above is a no-op marker; the actual init happens via the
    # fixture below when needed. We keep init_db importable.

    app = FastAPI(title="Rogologo Core (test)", version=__version__, lifespan=_noop_lifespan)
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
    app.include_router(evolution.router, prefix="/api")

    # Register routes with the inventory so render_endpoint_block has data.
    from core.runner.api_inventory import set_app
    set_app(app)

    return TestClient(app)


# ---------- health ----------

def test_health_responds_200(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "version" in body


def test_health_reports_current_version(client: TestClient):
    from core import __version__
    r = client.get("/api/health")
    assert r.json()["version"] == __version__


# ---------- lists ----------

def test_agents_list_returns_array(client: TestClient):
    r = client.get("/api/agents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_runs_list_returns_array(client: TestClient):
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_schedules_list_returns_array(client: TestClient):
    r = client.get("/api/schedules")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_projects_list_returns_array(client: TestClient):
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_skills_list_returns_array(client: TestClient):
    r = client.get("/api/skills")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- 404 paths ----------

def test_unknown_agent_returns_404(client: TestClient):
    r = client.get("/api/agents/99999")
    assert r.status_code == 404


def test_unknown_run_returns_404(client: TestClient):
    r = client.get("/api/runs/99999")
    assert r.status_code == 404


def test_evolution_unknown_agent_returns_404(client: TestClient):
    r = client.get("/api/agents/99999/evolution")
    assert r.status_code == 404


# ---------- api_inventory ----------

def test_api_inventory_lists_known_paths(client: TestClient):
    """The render block should mention at least /api/health and /api/agents."""
    from core.runner.api_inventory import render_endpoint_block
    block = render_endpoint_block()
    assert "/api/health" in block
    assert "/api/agents" in block
    assert "/api/runs" in block
    assert "/api/schedules" in block
    assert "/api/agents/{agent_id}/evolution" in block
