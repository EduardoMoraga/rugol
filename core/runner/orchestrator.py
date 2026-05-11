"""RuntimeOrchestrator — single source of truth for "an agent runs now".

Concurrency-bounded queue. Persists to DB. Emits bus events. Survives crashes.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from core.bus import bus
from core.config import get_settings
from core.db import async_session_factory
from core.db.models import Agent, Project, Run
from core.memory import build_memory_block
from core.runner.claude_runner import run_agent
from core.soul import (
    SOUL_TOOL_NAMES,
    build_soul_context,
    build_soul_mcp_server,
    classify,
    model_for_track,
    wrap_prompt_for_s2,
)
from core.soul.evolution import (
    current_body as evolution_current_body,
    load_lineage,
    pick_version_for_run,
    record_metrics,
)

logger = logging.getLogger(__name__)


def _build_project_context(project: Project) -> str | None:
    """Render project mission + lessons as a system-prompt anchor.

    Capa 3: every run inside a project sees this context appended to the
    system prompt — the mission keeps the agent anchored, the lessons
    encode what the team has already learned to avoid repeating mistakes.
    Returns None when there's nothing useful to inject.
    """
    parts: list[str] = []
    mission = (project.mission or "").strip()
    if mission:
        parts.append(f"## Project mission\n{mission}")
    lessons = project.lessons or []
    if lessons:
        rendered = []
        for l in lessons:
            if not isinstance(l, dict):
                continue
            text = str(l.get("text") or "").strip()
            kind = str(l.get("kind") or "lesson").strip().upper()
            if text:
                rendered.append(f"- [{kind}] {text}")
        if rendered:
            parts.append(
                "## Project lessons (read these BEFORE acting — they reflect what the team learned the hard way)\n"
                + "\n".join(rendered)
            )
    return ("\n\n".join(parts)) if parts else None


@dataclass
class RunRequest:
    agent_name: str
    prompt: str
    source: str  # schedule|telegram|slack|dashboard|api|devils-advocate
    schedule_id: int | None = None
    session_id: str | None = None
    metadata: dict | None = None
    # Capa 4: System 1/2 selector overrides the agent's default model
    # ("fast" → haiku, "deep" → opus). None means use the agent's model.
    model_override: str | None = None
    # Capa 4: when true, after this run completes, the orchestrator
    # spawns a critique run that challenges the answer.
    seek_devils_advocate: bool = False
    # Internal: the parent run id when this is the devil's advocate run.
    advocate_for_run_id: int | None = None


class RuntimeOrchestrator:
    """Bounded concurrent runner. One per process."""

    def __init__(self, max_concurrent: int, workspace_dir: Path) -> None:
        self._sem = asyncio.Semaphore(max_concurrent)
        self._workspace = workspace_dir
        self._active: dict[int, asyncio.Task] = {}

    async def enqueue(self, req: RunRequest) -> int:
        """Persist a Run row and spawn the runner task. Returns run_id."""
        # Soul-2 (ADR-007): classify the request BEFORE we touch the DB so a
        # slow Haiku call does not hold a SQLAlchemy connection open. Bypasses
        # gracefully when dual-track is disabled or the caller forced a model.
        dispatch_decision = await classify(
            req.prompt,
            agent_name=req.agent_name,
            model_override=req.model_override,
            workspace_dir=self._workspace,
        )

        async with async_session_factory() as session:
            agent = (await session.execute(
                select(Agent)
                .where(Agent.name == req.agent_name)
                .options(selectinload(Agent.project))
            )).scalar_one_or_none()
            if agent is None:
                raise ValueError(f"Agent not found: {req.agent_name}")

            # Run count BEFORE we insert this one, so "this is run #N" matches
            # what the soul block claims to the agent.
            prior_run_count = int(
                (await session.execute(
                    select(func.count(Run.id)).where(Run.agent_id == agent.id)
                )).scalar_one() or 0
            )
            last_run_at_iso = (
                agent.last_run_at.isoformat() if agent.last_run_at else None
            )

            run = Run(
                agent_id=agent.id,
                schedule_id=req.schedule_id,
                source=req.source,
                prompt=req.prompt,
                session_id=req.session_id,
                status="running",
                # Stamp dispatcher decision when it actually ran (not bypassed).
                track=None if dispatch_decision.bypassed else dispatch_decision.track,
                classifier_confidence=(
                    None if dispatch_decision.bypassed else dispatch_decision.confidence
                ),
                classifier_rationale=(
                    None if dispatch_decision.bypassed else dispatch_decision.rationale
                ),
            )
            session.add(run)
            await session.flush()
            run_id = run.id
            agent.status = "running"
            agent.last_run_at = dt.datetime.now(dt.timezone.utc)
            agent_name_snapshot = agent.name
            agent_description_snapshot = agent.description or ""
            agent_default_model_snapshot = agent.model
            agent_body_snapshot = agent.body or ""
            project = agent.project
            project_context = _build_project_context(project) if project else None
            # v0.6.x — Sprint B: per-agent file-based memory. Read the agent's
            # MEMORY.md index + memory files and append a "Tu memoria
            # persistente" block. Cumulative agent knowledge across runs.
            memory_block = build_memory_block(agent.name)
            if memory_block:
                project_context = (
                    f"{project_context}\n\n{memory_block}"
                    if project_context
                    else memory_block
                )
            await session.commit()

        # ADR-006 Soul Layer: identity + auto-memory rules block, plus the
        # in-process MCP server bound to this agent's name. Built outside
        # the DB session so a slow filesystem scan can't hold the connection.
        soul_context = build_soul_context(
            agent_name=agent_name_snapshot,
            description=agent_description_snapshot,
            run_count=prior_run_count,
            last_run_at_iso=last_run_at_iso,
        )
        soul_mcp_server = build_soul_mcp_server(agent_name_snapshot)

        # ADR-008 Soul-3: resolve which lineage version executes this run.
        # If the agent has no archive, version_id is None and we fall back
        # to the body persisted on the Agent row. If an archive exists, the
        # router picks current (or an A/B branch when enabled).
        chosen_version_id = pick_version_for_run(agent_name_snapshot, run_id)
        if chosen_version_id is not None:
            effective_agent_body = evolution_current_body(
                agent_name_snapshot, agent_body_snapshot
            )
            # Stamp version_id on the Run row in a tiny follow-up tx so the
            # dashboard can attribute metrics correctly.
            async with async_session_factory() as session:
                run_row = await session.get(Run, run_id)
                if run_row is not None:
                    run_row.agent_version_id = chosen_version_id
                    await session.commit()
        else:
            effective_agent_body = agent_body_snapshot

        await bus.publish("run:started", {
            "run_id": run_id,
            "agent": req.agent_name,
            "source": req.source,
            "advocate_for_run_id": req.advocate_for_run_id,
            "track": dispatch_decision.track if not dispatch_decision.bypassed else None,
            "agent_version_id": chosen_version_id,
        })

        # Resolve the effective model in priority order:
        #   1. Explicit model_override from the caller (Capa 4).
        #   2. Dispatcher decision (Soul-2): s1 → Haiku, s2 → agent default.
        #   3. Agent's configured default model.
        if req.model_override:
            effective_model = req.model_override
        elif not dispatch_decision.bypassed:
            effective_model = model_for_track(
                dispatch_decision.track, agent_default_model_snapshot
            )
        else:
            effective_model = agent_default_model_snapshot

        # Soul-2: when dispatcher routed S2 and plan-then-execute is on,
        # wrap the prompt so the model produces a plan + critique + answer
        # in a single round-trip. Skipped for devil's advocate (which has
        # its own meta-prompt) and bypassed runs.
        runner_prompt = req.prompt
        settings = get_settings()
        if (
            settings.SOUL_PLAN_THEN_EXECUTE_ENABLED
            and not dispatch_decision.bypassed
            and dispatch_decision.track == "s2"
            and not req.advocate_for_run_id
        ):
            runner_prompt = wrap_prompt_for_s2(req.prompt)

        task = asyncio.create_task(
            self._execute(
                run_id, req,
                model=effective_model,
                tools=agent.tools,
                project_context=project_context,
                agent_id=agent.id,
                mcp_servers=agent.mcp_servers,
                soul_context=soul_context,
                soul_mcp_server=soul_mcp_server,
                runner_prompt=runner_prompt,
                agent_body=effective_agent_body,
                agent_name_for_metrics=agent_name_snapshot,
                version_id_for_metrics=chosen_version_id,
            )
        )
        self._active[run_id] = task
        return run_id

    async def _execute(
        self,
        run_id: int,
        req: RunRequest,
        model: str,
        tools: list[str] | None = None,
        project_context: str | None = None,
        agent_id: int | None = None,
        mcp_servers: dict | None = None,
        soul_context: str | None = None,
        soul_mcp_server=None,
        runner_prompt: str | None = None,
        agent_body: str | None = None,
        agent_name_for_metrics: str | None = None,
        version_id_for_metrics: str | None = None,
    ) -> None:
        async with self._sem:
            try:
                result = await run_agent(
                    agent_name=req.agent_name,
                    prompt=runner_prompt if runner_prompt is not None else req.prompt,
                    workspace_dir=self._workspace,
                    model=model,
                    session_id=req.session_id,
                    run_id=run_id,
                    tools=tools,
                    project_context=project_context,
                    mcp_servers=mcp_servers,
                    soul_context=soul_context,
                    soul_mcp_server=soul_mcp_server,
                    soul_tool_names=SOUL_TOOL_NAMES,
                    agent_body=agent_body,
                )
                await self._mark_completed(run_id, result)
                # Soul-3 (ADR-008): fold this run's cost into the version's
                # rolling average. Best-effort — never block the happy path
                # on archive bookkeeping.
                if agent_name_for_metrics and version_id_for_metrics:
                    try:
                        record_metrics(
                            agent_name_for_metrics, version_id_for_metrics,
                            cost_usd=float(result.cost_usd or 0.0),
                            latency_ms=0.0,  # filled by adapters that time the call
                        )
                    except Exception:
                        logger.exception(
                            "evolution metrics record failed for %s/%s",
                            agent_name_for_metrics, version_id_for_metrics,
                        )
                # Capa 4: spawn the devil's advocate run after the original
                # finishes. Same agent, same project context, opus model,
                # critique meta-prompt. Detached task so the user's primary
                # run isn't held back.
                if req.seek_devils_advocate and not req.advocate_for_run_id:
                    asyncio.create_task(
                        self._spawn_devils_advocate(
                            req.agent_name, req.prompt,
                            primary_run_id=run_id,
                            primary_text=result.final_text,
                        )
                    )
            except asyncio.CancelledError:
                await self._mark_status(run_id, "cancelled", error="cancelled by user")
                raise
            except Exception as e:
                logger.exception("run %s failed", run_id)
                await self._mark_status(run_id, "failed", error=str(e))
            finally:
                self._active.pop(run_id, None)
                # Capa 3: best-effort fire-and-forget reflection. Never let
                # this throw or the user sees a stale run row.
                if agent_id is not None:
                    asyncio.create_task(
                        self._maybe_reflect(agent_id, req.agent_name)
                    )

    async def _spawn_devils_advocate(
        self,
        agent_name: str,
        original_prompt: str,
        primary_run_id: int,
        primary_text: str,
    ) -> None:
        """Spawn a critique run on the same agent. Uses opus to maximize the
        chance of catching real problems, not generic objections."""
        try:
            critique_prompt = (
                "You are this same agent's devil's advocate. The agent just produced an "
                "answer; your job is to challenge it specifically and helpfully — not "
                "to be contrarian for sport.\n\n"
                f"## Original prompt the user sent\n{original_prompt}\n\n"
                f"## The agent's answer\n{primary_text}\n\n"
                "## Your task\n"
                "1. Identify the single weakest assumption in the answer (be specific, "
                "quote it).\n"
                "2. Identify ONE blind spot — something the agent did not consider but "
                "should have, given the prompt.\n"
                "3. Propose a sharper version of the answer in 1-3 sentences.\n\n"
                "Be useful, not academic. If the answer is genuinely solid, say so and "
                "stop — false positives waste the user's attention."
            )
            await self.enqueue(RunRequest(
                agent_name=agent_name,
                prompt=critique_prompt,
                source="devils-advocate",
                model_override="claude-opus-4-7",
                advocate_for_run_id=primary_run_id,
            ))
        except Exception:
            logger.exception("devil's advocate spawn failed for run %s", primary_run_id)

    async def _maybe_reflect(self, agent_id: int, agent_name: str) -> None:
        """If the agent is due for reflection, spawn it. Errors are swallowed."""
        try:
            from core.improvements.trigger import is_due
            from core.improvements.reflector import propose_improvement
            if not await is_due(agent_id):
                return
            logger.info("reflection due for agent %s — spawning", agent_name)
            imp_id = await propose_improvement(agent_id, self._workspace)
            if imp_id is not None:
                await bus.publish("improvement:proposed", {
                    "id": imp_id, "agent": agent_name, "agent_id": agent_id,
                })
        except Exception:
            logger.exception("reflection cycle failed for agent %s", agent_name)

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
            "session_id": result.session_id,  # v0.6: needed by adapters that
            # want to thread conversational context across turns.
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
