"""File-based lineage archive for one agent.

Storage layout
--------------
agent-soul/<agent_name>/
  lineage.json
  versions/
    001.md
    002.md
    ...

lineage.json schema (versioned by `schema` field):

    {
      "schema": 1,
      "current": "002",
      "versions": [
        {
          "id": "001",
          "parent": null,
          "created_at": "2026-05-10T18:00:00+00:00",
          "status": "active|archived|proposed|rejected|accepted",
          "rationale": "free text",
          "hypothesis": "what should improve",
          "metrics": {"runs": 0, "avg_cost_usd": 0.0, "avg_latency_ms": 0.0},
          "validation_score": null
        }
      ]
    }

Why files + JSON instead of DB tables: bodies are big text blobs that are
also written/read by humans; lineage trees stay small (dozens of versions
per agent at most); diffing/auditing is trivial with `git`.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 1
VALID_STATUSES = {"active", "archived", "proposed", "rejected", "accepted"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _slug(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "agent"


def archive_dir(agent_name: str) -> Path:
    return _repo_root() / "agent-soul" / _slug(agent_name)


def _versions_dir(agent_name: str) -> Path:
    return archive_dir(agent_name) / "versions"


def _lineage_path(agent_name: str) -> Path:
    return archive_dir(agent_name) / "lineage.json"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _next_version_id(existing_ids: Iterable[str]) -> str:
    """Pick the next numeric id (left-padded to 3 digits)."""
    nums: list[int] = []
    for vid in existing_ids:
        try:
            nums.append(int(vid))
        except ValueError:
            continue
    return f"{(max(nums) + 1 if nums else 1):03d}"


@dataclass
class Version:
    id: str
    parent: str | None
    created_at: str
    status: str
    rationale: str = ""
    hypothesis: str = ""
    metrics: dict = field(default_factory=lambda: {"runs": 0, "avg_cost_usd": 0.0, "avg_latency_ms": 0.0})
    validation_score: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Lineage:
    current: str
    versions: list[Version]
    schema: int = SCHEMA_VERSION

    def get(self, version_id: str) -> Version | None:
        for v in self.versions:
            if v.id == version_id:
                return v
        return None

    def as_dict(self) -> dict:
        return {
            "schema": self.schema,
            "current": self.current,
            "versions": [v.as_dict() for v in self.versions],
        }


def load_lineage(agent_name: str) -> Lineage | None:
    path = _lineage_path(agent_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("could not parse lineage for %s: %s", agent_name, e)
        return None
    versions = [Version(**v) for v in data.get("versions", [])]
    return Lineage(
        current=str(data.get("current") or (versions[0].id if versions else "001")),
        versions=versions,
        schema=int(data.get("schema") or SCHEMA_VERSION),
    )


def _save_lineage(agent_name: str, lineage: Lineage) -> None:
    archive_dir(agent_name).mkdir(parents=True, exist_ok=True)
    _versions_dir(agent_name).mkdir(parents=True, exist_ok=True)
    _lineage_path(agent_name).write_text(
        json.dumps(lineage.as_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _version_path(agent_name: str, version_id: str) -> Path:
    return _versions_dir(agent_name) / f"{version_id}.md"


def load_version_body(agent_name: str, version_id: str) -> str | None:
    path = _version_path(agent_name, version_id)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def ensure_archive(agent_name: str, seed_body: str) -> Lineage:
    """Create an archive seeded with the agent's current body if none exists.

    Idempotent: if the archive already has versions, return it untouched.
    The seed becomes version 001 with status='active', no parent, current=001.
    """
    existing = load_lineage(agent_name)
    if existing is not None and existing.versions:
        return existing
    version_id = "001"
    v = Version(
        id=version_id,
        parent=None,
        created_at=_now_iso(),
        status="active",
        rationale="initial seed from agent body",
        hypothesis="",
    )
    lineage = Lineage(current=version_id, versions=[v])
    _save_lineage(agent_name, lineage)
    _version_path(agent_name, version_id).parent.mkdir(parents=True, exist_ok=True)
    _version_path(agent_name, version_id).write_text(
        (seed_body or "").strip() + "\n", encoding="utf-8"
    )
    logger.info("soul-evolution: seeded archive for %s with version 001", agent_name)
    return lineage


def current_body(agent_name: str, fallback_body: str) -> str:
    """Return the body of the current active version, or fallback if no archive."""
    lineage = load_lineage(agent_name)
    if lineage is None or not lineage.versions:
        return fallback_body or ""
    body = load_version_body(agent_name, lineage.current)
    if body is None:
        return fallback_body or ""
    return body


def list_versions(agent_name: str) -> list[Version]:
    lineage = load_lineage(agent_name)
    return list(lineage.versions) if lineage else []


def active_version_ids(agent_name: str) -> list[str]:
    """Versions eligible for A/B routing (status='active')."""
    lineage = load_lineage(agent_name)
    if lineage is None:
        return []
    return [v.id for v in lineage.versions if v.status == "active"]


def propose_version(
    agent_name: str,
    body: str,
    *,
    rationale: str = "",
    hypothesis: str = "",
    parent: str | None = None,
) -> str:
    """Persist a proposed candidate version. Returns its id.

    The archive is created on demand if it didn't exist; this is the
    one entry point that bypasses ensure_archive() so the proposer can
    bootstrap an archive AND propose a candidate in the same call.
    """
    lineage = load_lineage(agent_name)
    if lineage is None:
        # Brand new archive: seed version 001 from the parent body (which
        # is the agent's pre-proposal state).
        lineage = ensure_archive(agent_name, body)
    next_id = _next_version_id(v.id for v in lineage.versions)
    parent_id = parent or lineage.current
    v = Version(
        id=next_id,
        parent=parent_id,
        created_at=_now_iso(),
        status="proposed",
        rationale=rationale.strip(),
        hypothesis=hypothesis.strip(),
    )
    lineage.versions.append(v)
    _save_lineage(agent_name, lineage)
    _version_path(agent_name, next_id).write_text(
        (body or "").strip() + "\n", encoding="utf-8"
    )
    logger.info("soul-evolution: proposed version %s for %s (parent=%s)", next_id, agent_name, parent_id)
    return next_id


def _update_status(
    agent_name: str,
    version_id: str,
    new_status: str,
    *,
    set_current: bool = False,
    archive_siblings: bool = False,
) -> bool:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {new_status}")
    lineage = load_lineage(agent_name)
    if lineage is None:
        return False
    v = lineage.get(version_id)
    if v is None:
        return False
    v.status = new_status
    if set_current:
        lineage.current = version_id
    if archive_siblings:
        for other in lineage.versions:
            if other.id != version_id and other.status == "active":
                other.status = "archived"
    _save_lineage(agent_name, lineage)
    return True


def accept_version(agent_name: str, version_id: str) -> bool:
    """Promote a proposed version to active, set as current, archive siblings."""
    return _update_status(
        agent_name, version_id, "active",
        set_current=True, archive_siblings=True,
    )


def reject_version(agent_name: str, version_id: str) -> bool:
    return _update_status(agent_name, version_id, "rejected")


def branch_to(agent_name: str, version_id: str) -> bool:
    """Promote a proposed version to active WITHOUT archiving the current.

    Used to start A/B testing two versions side by side.
    """
    return _update_status(agent_name, version_id, "active", set_current=False)


def rollback_to(agent_name: str, version_id: str) -> bool:
    """Set the given version as current. Versions newer than it are archived."""
    lineage = load_lineage(agent_name)
    if lineage is None:
        return False
    target = lineage.get(version_id)
    if target is None:
        return False
    target.status = "active"
    lineage.current = version_id
    # Archive any version with id numerically greater than the target.
    try:
        target_num = int(version_id)
    except ValueError:
        target_num = -1
    for v in lineage.versions:
        if v.id == version_id:
            continue
        try:
            if int(v.id) > target_num and v.status == "active":
                v.status = "archived"
        except ValueError:
            continue
    _save_lineage(agent_name, lineage)
    return True


def record_metrics(
    agent_name: str,
    version_id: str,
    *,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
) -> None:
    """Fold a finished run's metrics into the version's running average.

    Cheap incremental update — keeps `metrics.runs` honest and rolls the
    averages without storing every datapoint.
    """
    lineage = load_lineage(agent_name)
    if lineage is None:
        return
    v = lineage.get(version_id)
    if v is None:
        return
    runs = int(v.metrics.get("runs", 0) or 0)
    avg_cost = float(v.metrics.get("avg_cost_usd", 0.0) or 0.0)
    avg_lat = float(v.metrics.get("avg_latency_ms", 0.0) or 0.0)
    new_runs = runs + 1
    v.metrics["runs"] = new_runs
    v.metrics["avg_cost_usd"] = (avg_cost * runs + cost_usd) / new_runs
    v.metrics["avg_latency_ms"] = (avg_lat * runs + latency_ms) / new_runs
    _save_lineage(agent_name, lineage)
