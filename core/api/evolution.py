"""Soul-3 evolutionary archive REST endpoints (ADR-008).

Routes live under /api/agents/{agent_id}/evolution/... because the
archive is per-agent. The dashboard renders the lineage as a tree and
calls these endpoints for the lifecycle actions.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from core.db import async_session_factory
from core.db.models import Agent
from core.soul.evolution import archive as ar
from core.soul.evolution.proposer import propose_mutations
from core.soul.evolution.validator import validate_candidate

router = APIRouter(prefix="/agents/{agent_id}/evolution", tags=["evolution"])


def _workspace() -> Path:
    # core/api/evolution.py → core/api → core → repo
    return Path(__file__).resolve().parent.parent.parent


async def _resolve_agent_name(agent_id: int) -> str:
    async with async_session_factory() as session:
        agent = await session.get(Agent, agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return agent.name


async def _resolve_agent_name_and_body(agent_id: int) -> tuple[str, str]:
    async with async_session_factory() as session:
        agent = await session.get(Agent, agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return agent.name, agent.body or ""


@router.get("")
async def get_evolution(agent_id: int) -> dict:
    """Return the agent's lineage as JSON. Seeds the archive on first call."""
    agent_name, agent_body = await _resolve_agent_name_and_body(agent_id)
    lineage = ar.load_lineage(agent_name)
    if lineage is None:
        lineage = ar.ensure_archive(agent_name, agent_body)
    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "current": lineage.current,
        "active": ar.active_version_ids(agent_name),
        "versions": [v.as_dict() for v in lineage.versions],
    }


@router.get("/{version_id}/body")
async def get_version_body(agent_id: int, version_id: str) -> dict:
    agent_name = await _resolve_agent_name(agent_id)
    body = ar.load_version_body(agent_name, version_id)
    if body is None:
        raise HTTPException(status_code=404, detail="version not found")
    return {"version_id": version_id, "body": body}


@router.post("/propose", status_code=202)
async def propose(agent_id: int, max_candidates: int = 2) -> dict:
    """Run the proposer to generate new candidate versions."""
    new_ids = await propose_mutations(
        agent_id, _workspace(), max_candidates=max_candidates,
    )
    return {"proposed_version_ids": new_ids}


@router.post("/{version_id}/validate", status_code=202)
async def validate(
    agent_id: int,
    version_id: str,
    payload: dict | None = Body(default=None),  # noqa: B008  (FastAPI dependency pattern)
) -> dict:
    """Score a proposed version. Result is informational; humans decide."""
    agent_name = await _resolve_agent_name(agent_id)
    summary = (payload or {}).get("recent_runs_summary") or ""
    result = await validate_candidate(
        agent_name, version_id, _workspace(),
        recent_runs_summary=summary,
    )
    # Persist the score on the version so the UI can show it without re-running.
    lineage = ar.load_lineage(agent_name)
    if lineage is not None:
        v = lineage.get(version_id)
        if v is not None:
            v.validation_score = result.score
            # archive module exposes the save through update_status helpers,
            # but score-only updates use this small path:
            ar.archive_dir(agent_name).mkdir(parents=True, exist_ok=True)
            from json import dumps
            (ar.archive_dir(agent_name) / "lineage.json").write_text(
                dumps(lineage.as_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    return result.as_dict()


@router.post("/{version_id}/accept")
async def accept(agent_id: int, version_id: str) -> dict:
    agent_name = await _resolve_agent_name(agent_id)
    ok = ar.accept_version(agent_name, version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="version not found")
    return {"status": "accepted", "version_id": version_id}


@router.post("/{version_id}/reject")
async def reject(agent_id: int, version_id: str) -> dict:
    agent_name = await _resolve_agent_name(agent_id)
    ok = ar.reject_version(agent_name, version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="version not found")
    return {"status": "rejected", "version_id": version_id}


@router.post("/{version_id}/branch")
async def branch(agent_id: int, version_id: str) -> dict:
    agent_name = await _resolve_agent_name(agent_id)
    ok = ar.branch_to(agent_name, version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="version not found")
    return {"status": "branched", "version_id": version_id}


@router.post("/{version_id}/rollback")
async def rollback(agent_id: int, version_id: str) -> dict:
    agent_name = await _resolve_agent_name(agent_id)
    ok = ar.rollback_to(agent_name, version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="version not found")
    return {"status": "rolled-back", "version_id": version_id}
