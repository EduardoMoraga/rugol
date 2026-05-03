"""Architect — propose an agentic infrastructure, review, deploy."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.architect import Proposal, deploy as deploy_proposal, propose

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/architect", tags=["architect"])


class ProposeBody(BaseModel):
    idea: str = Field(min_length=4, max_length=4000)
    constraints: str = ""


class DeployBody(BaseModel):
    proposal: dict


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
    res = await deploy_proposal(proposal)
    return res.as_dict()
