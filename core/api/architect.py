"""Architect — propose an agentic infrastructure, review, deploy."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import runtime_state
from core.architect import Proposal, deploy as deploy_proposal, propose

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/architect", tags=["architect"])


class ProposeBody(BaseModel):
    idea: str = Field(min_length=4, max_length=4000)
    constraints: str = ""


class DeployBody(BaseModel):
    proposal: dict
    # Capa 5: optional install dir overrides for this deploy. Missing or empty
    # → use the global settings.agents_dir / settings.skills_dir (current
    # behavior preserved). Helpful when the user wants this team to land in
    # a specific folder without changing the global setting.
    target_agents_dir: str | None = None
    target_skills_dir: str | None = None


@router.post("/propose")
async def propose_endpoint(body: ProposeBody) -> dict:
    try:
        p = await propose(idea=body.idea, constraints=body.constraints)
    except ValueError as e:
        # ValueError → user-facing config / parsing problem. Echo the message
        # in full so the dashboard can show it (it includes a model-output
        # snippet on parse failures).
        logger.warning("architect.propose unprocessable: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("architect.propose failed")
        raise HTTPException(status_code=500, detail=str(e))
    return p.as_dict()


@router.post("/deploy")
async def deploy_endpoint(body: DeployBody) -> dict:
    try:
        proposal = Proposal.from_dict(body.proposal)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid proposal payload: {e}")
    if not proposal.agents:
        raise HTTPException(status_code=400, detail="Proposal has no agents to deploy.")
    target_agents = Path(body.target_agents_dir) if body.target_agents_dir else None
    target_skills = Path(body.target_skills_dir) if body.target_skills_dir else None
    res = await deploy_proposal(
        proposal,
        target_agents_dir=target_agents,
        target_skills_dir=target_skills,
    )
    return res.as_dict()


@router.get("/install-dirs")
async def install_dirs() -> dict:
    """Returns the active default install paths so the dashboard can
    pre-fill the dir picker without a separate Settings call."""
    return {
        "agents_dir": str(runtime_state.agents_dir()),
        "skills_dir": str(runtime_state.skills_dir()),
    }
