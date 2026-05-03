"""Take a (possibly user-edited) Proposal and make it real on disk + DB."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from core import runtime_state
from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, Schedule
from core.ontology import get_ontology
from core.registry.service import upsert_agent_file, upsert_skill_file
from core.scheduler import get_scheduler

from .proposer import Proposal

logger = logging.getLogger(__name__)


@dataclass
class DeployResult:
    agents_created: list[str] = field(default_factory=list)
    agents_skipped: list[dict] = field(default_factory=list)
    skills_created: list[str] = field(default_factory=list)
    skills_skipped: list[dict] = field(default_factory=list)
    schedules_created: list[int] = field(default_factory=list)
    schedules_skipped: list[dict] = field(default_factory=list)
    ontology_edges_created: int = 0

    def as_dict(self) -> dict:
        return self.__dict__


def _agent_md(name: str, model: str, description: str, body: str) -> str:
    esc = description.replace('"', '\\"')
    return (
        "---\n"
        f"name: {name}\n"
        f"model: {model}\n"
        f'description: "{esc}"\n'
        "---\n\n"
        + body.strip() + "\n"
    )


def _skill_md(name: str, description: str, body: str) -> str:
    esc = description.replace('"', '\\"')
    return (
        "---\n"
        f"name: {name}\n"
        f'description: "{esc}"\n'
        "---\n\n"
        + body.strip() + "\n"
    )


async def deploy(proposal: Proposal) -> DeployResult:
    res = DeployResult()
    agents_dir = runtime_state.agents_dir()
    skills_dir = runtime_state.skills_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    # 1. Agents
    for a in proposal.agents:
        target = agents_dir / f"{a.name}.md"
        if target.exists():
            res.agents_skipped.append({"name": a.name, "reason": "file already exists"})
            continue
        target.write_text(_agent_md(a.name, a.model, a.description, a.body), encoding="utf-8")
        await upsert_agent_file(target)
        res.agents_created.append(a.name)

    # 2. Skills
    for s in proposal.skills:
        target = skills_dir / f"{s.name}.md"
        if target.exists():
            res.skills_skipped.append({"name": s.name, "reason": "file already exists"})
            continue
        target.write_text(_skill_md(s.name, s.description, s.body), encoding="utf-8")
        await upsert_skill_file(target)
        res.skills_created.append(s.name)

    # 3. Schedules — need agent IDs from the DB.
    if proposal.schedules:
        scheduler = get_scheduler()
        async with async_session_factory() as session:
            for sch in proposal.schedules:
                agent_row = (await session.execute(
                    select(Agent).where(Agent.name == sch.agent_name)
                )).scalar_one_or_none()
                if agent_row is None:
                    res.schedules_skipped.append({
                        "agent_name": sch.agent_name,
                        "reason": "agent does not exist (was it skipped?)",
                    })
                    continue
                row = Schedule(
                    agent_id=agent_row.id,
                    cron_expr=sch.cron_expr,
                    prompt=sch.prompt,
                    enabled=True,
                )
                session.add(row)
                await session.flush()
                schedule_id = row.id
                try:
                    scheduler.add_cron(schedule_id, agent_row.name, sch.prompt, sch.cron_expr)
                except Exception as e:
                    res.schedules_skipped.append({
                        "agent_name": sch.agent_name,
                        "reason": f"invalid cron: {e}",
                    })
                    await session.rollback()
                    continue
                await session.commit()
                res.schedules_created.append(schedule_id)

    # 4. Ontology seeds
    if proposal.ontology_seeds:
        store = get_ontology()
        for triple in proposal.ontology_seeds:
            try:
                await store.add_edge(triple.src, triple.predicate, triple.dst)
                res.ontology_edges_created += 1
            except Exception:
                logger.exception("failed to add seed triple %s", triple)

    await bus.publish("architect:deployed", res.as_dict())
    return res
