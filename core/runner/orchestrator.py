"""RuntimeOrchestrator — single source of truth for "an agent runs now".

Concurrency-bounded queue. Persists to DB. Emits bus events. Survives crashes.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from core.bus import bus
from core.config import get_settings
from core.db import async_session_factory
from core.db.models import Agent, Run
from core.runner.claude_runner import run_agent

logger = logging.getLogger(__name__)


@dataclass
class RunRequest:
    agent_name: str
    prompt: str
    source: str  # schedule|telegram|slack|dashboard|api
    schedule_id: int | None = None
    session_id: str | None = None
    metadata: dict | None = None


class RuntimeOrchestrator:
    """Bounded concurrent runner. One per process."""

    def __init__(self, max_concurrent: int, workspace_dir: Path) -> None:
        self._sem = asyncio.Semaphore(max_concurrent)
        self._workspace = workspace_dir
        self._active: dict[int, asyncio.Task] = {}

    async def enqueue(self, req: RunRequest) -> int:
        """Persist a Run row and spawn the runner task. Returns run_id."""
        async with async_session_factory() as session:
            agent = (await session.execute(
                select(Agent).where(Agent.name == req.agent_name)
            )).scalar_one_or_none()
            if agent is None:
                raise ValueError(f"Agent not found: {req.agent_name}")

            run = Run(
                agent_id=agent.id,
                schedule_id=req.schedule_id,
                source=req.source,
                prompt=req.prompt,
                session_id=req.session_id,
                status="running",
            )
            session.add(run)
            await session.flush()
            run_id = run.id
            agent.status = "running"
            agent.last_run_at = dt.datetime.now(dt.timezone.utc)
            await session.commit()

        await bus.publish("run:started", {
            "run_id": run_id,
            "agent": req.agent_name,
            "source": req.source,
        })

        task = asyncio.create_task(
            self._execute(run_id, req, model=agent.model, tools=agent.tools)
        )
        self._active[run_id] = task
        return run_id

    async def _execute(
        self,
        run_id: int,
        req: RunRequest,
        model: str,
        tools: list[str] | None = None,
    ) -> None:
        async with self._sem:
            try:
                result = await run_agent(
                    agent_name=req.agent_name,
                    prompt=req.prompt,
                    workspace_dir=self._workspace,
                    model=model,
                    session_id=req.session_id,
                    run_id=run_id,
                    tools=tools,
                )
                await self._mark_completed(run_id, result)
            except asyncio.CancelledError:
                await self._mark_status(run_id, "cancelled", error="cancelled by user")
                raise
            except Exception as e:
                logger.exception("run %s failed", run_id)
                await self._mark_status(run_id, "failed", error=str(e))
            finally:
                self._active.pop(run_id, None)

    async def _mark_completed(self, run_id: int, result) -> None:
        agent_name = ""
        async with async_session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None:
                return
            run.status = "completed"
            run.ended_at = dt.datetime.now(dt.timezone.utc)
            run.input_tokens = result.input_tokens
            run.output_tokens = result.output_tokens
            run.cost_usd = result.cost_usd
            run.session_id = result.session_id
            run.final_text = result.final_text
            agent = await session.get(Agent, run.agent_id)
            if agent:
                agent.status = "idle"
                agent_name = agent.name
            await session.commit()
        await bus.publish("run:completed", {
            "run_id": run_id,
            "agent": agent_name,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
            "final_text": result.final_text[:4000],
        })

    async def _mark_status(self, run_id: int, status: str, error: str = "") -> None:
        agent_name = ""
        async with async_session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None:
                return
            run.status = status
            run.ended_at = dt.datetime.now(dt.timezone.utc)
            run.error_message = error or None
            agent = await session.get(Agent, run.agent_id)
            if agent:
                agent.status = "error" if status == "failed" else "idle"
                agent_name = agent.name
            await session.commit()
        await bus.publish(f"run:{status}", {"run_id": run_id, "agent": agent_name, "error": error})

    def cancel(self, run_id: int) -> bool:
        task = self._active.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    @property
    def active_count(self) -> int:
        return len(self._active)


_orchestrator: RuntimeOrchestrator | None = None


def get_orchestrator() -> RuntimeOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        settings = get_settings()
        _orchestrator = RuntimeOrchestrator(
            max_concurrent=settings.MAX_CONCURRENT_RUNS,
            workspace_dir=Path(__file__).resolve().parent.parent.parent,
        )
    return _orchestrator
