"""Architect — turn an idea into a deployable agentic infrastructure.

Two-step flow:
1. `proposer.propose(idea)` calls Claude with a meta-prompt and returns a
   structured `Proposal` (agents, skills, schedules, ontology seeds).
2. `deployer.deploy(proposal)` writes the .md files, registers schedules,
   and seeds the ontology.

Both steps are server-side. The frontend ships the proposal JSON between
them so the user can edit before deploying.
"""
from .deployer import DeployResult, deploy
from .proposer import (
    META_PROMPT,
    Proposal,
    ProposalAgent,
    ProposalProject,
    ProposalSchedule,
    ProposalSkill,
    ProposalTriple,
    propose,
)

__all__ = [
    "META_PROMPT",
    "Proposal",
    "ProposalAgent",
    "ProposalProject",
    "ProposalSchedule",
    "ProposalSkill",
    "ProposalTriple",
    "propose",
    "DeployResult",
    "deploy",
]
