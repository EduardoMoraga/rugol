"""Soul-3 evolutionary archive (ADR-008).

Each agent has a lineage of system-prompt versions persisted under
`agent-soul/<agent_name>/`. The reflector proposes mutations, the
validator scores them, the human (or A/B) decides which become default.
"""
from __future__ import annotations

from core.soul.evolution.archive import (
    Lineage,
    Version,
    accept_version,
    active_version_ids,
    branch_to,
    current_body,
    ensure_archive,
    list_versions,
    load_lineage,
    propose_version,
    record_metrics,
    reject_version,
    rollback_to,
)
from core.soul.evolution.router import pick_version_for_run

__all__ = [
    "Lineage",
    "Version",
    "accept_version",
    "active_version_ids",
    "branch_to",
    "current_body",
    "ensure_archive",
    "list_versions",
    "load_lineage",
    "propose_version",
    "record_metrics",
    "reject_version",
    "rollback_to",
    "pick_version_for_run",
]
