"""Soul-3 A/B router (ADR-008).

When multiple versions of an agent are simultaneously 'active', new runs
are distributed across them. Routing is deterministic by `run_id` so the
same run always sees the same version (useful for retries and debugging).

When SOUL_EVOLUTION_AB_ENABLED is False (default), the router always
returns the `current` version — making the archive read-only from the
runtime's perspective.
"""
from __future__ import annotations

import logging

from core.config import get_settings
from core.soul.evolution.archive import active_version_ids, load_lineage

logger = logging.getLogger(__name__)


def pick_version_for_run(agent_name: str, run_id: int | None) -> str | None:
    """Return the version_id this run should execute against, or None if
    the agent has no archive."""
    lineage = load_lineage(agent_name)
    if lineage is None or not lineage.versions:
        return None

    settings = get_settings()
    if not settings.SOUL_EVOLUTION_AB_ENABLED:
        return lineage.current

    active = active_version_ids(agent_name)
    if not active:
        return lineage.current
    if len(active) == 1:
        return active[0]

    # Deterministic round-robin keyed by run_id. Stable across retries,
    # uniform-ish over the long run.
    pivot = (run_id or 0) % len(active)
    chosen = active[pivot]
    logger.debug(
        "soul-evolution router: agent=%s active=%s pivot=%s chosen=%s",
        agent_name, active, pivot, chosen,
    )
    return chosen
