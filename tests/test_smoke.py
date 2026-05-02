"""Smoke tests — verify imports and basic wiring."""
from __future__ import annotations

import pytest


def test_imports():
    """All core modules import cleanly."""
    import core
    import core.api.agents
    import core.api.health
    import core.api.improvements
    import core.api.ontology
    import core.api.runs
    import core.api.schedules
    import core.api.stream
    import core.bus
    import core.config
    import core.db
    import core.db.models
    import core.improvements.reflector
    import core.improvements.trigger
    import core.ontology.store
    import core.registry.loader
    import core.registry.service
    import core.registry.watcher
    import core.runner.claude_runner
    import core.runner.orchestrator
    import core.scheduler.scheduler
    assert core.__version__


def test_settings_defaults():
    from core.config import get_settings
    s = get_settings()
    assert s.DEFAULT_MODEL.startswith("claude")
    assert s.MAX_CONCURRENT_RUNS >= 1


@pytest.mark.asyncio
async def test_bus_publish_subscribe():
    """Bus delivers events to matching subscribers."""
    import asyncio
    from core.bus import bus

    received = []

    async def consume():
        async for evt in bus.subscribe("test:*"):
            received.append(evt)
            if len(received) == 2:
                return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await bus.publish("test:one", {"x": 1})
    await bus.publish("other:topic", {"x": 2})  # should not match
    await bus.publish("test:two", {"x": 3})
    await asyncio.wait_for(task, timeout=2)

    assert len(received) == 2
    assert received[0].topic == "test:one"
    assert received[1].topic == "test:two"
