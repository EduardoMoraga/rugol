"""Agents CRUD + run-now."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from core import runtime_state
from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, Project, Run
from core.mcp import test_mcp_server
from core.registry.service import upsert_agent_file
from core.runner.orchestrator import RunRequest, get_orchestrator

router = APIRouter(prefix="/agents", tags=["agents"])

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
ALLOWED_MODELS = {
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-haiku-4-5",
}


class AgentDTO(BaseModel):
    id: int
    name: str
    model: str
    description: str
    status: str
    last_run_at: str | None = None
    project_id: int | None = None
    project_slug: str | None = None
    project_name: str | None = None
    project_color: str | None = None
    project_icon: str | None = None
    tools: list[str] | None = None  # Capa 5; None/[] → preset
    mcp_servers: dict | None = None  # Capa 8; per-agent MCP server configs


class RunNowBody(BaseModel):
    prompt: str
    session_id: str | None = None
    # Capa 4 — System 1 vs System 2 explicit. Overrides the agent's default
    # model choice based on the *type of thinking* the user expects:
    # - "fast"   → haiku   (heuristic, low-stakes, classification)
    # - "think"  → agent's own model (the default)
    # - "deep"   → opus    (deliberate, high-stakes, reasoning under uncertainty)
    task_type: str | None = None  # "fast" | "think" | "deep" | None
    # Capa 4 — devil's advocate. After the run completes, fire a second
    # synthetic run that critiques the first one. The critique becomes a
    # separate Run row with source="devils-advocate" so the user can promote
    # findings to project lessons.
    seek_devils_advocate: bool = False


class AgentSpec(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    model: str
    description: str = ""
    body: str
    project_slug: str | None = None        # ADR-005
    tools: list[str] | None = None         # Capa 5
    mcp_servers: dict | None = None        # Capa 8

    def to_markdown(self) -> str:
        # Build deterministic, valid YAML frontmatter.
        import json
        esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
        lines = ["---", f"name: {self.name}", f"model: {self.model}"]
        if self.project_slug:
            lines.append(f"project: {self.project_slug.strip().lower()}")
        if self.tools:
            tool_csv = ", ".join(t.strip() for t in self.tools if t.strip())
            if tool_csv:
                lines.append(f"tools: [{tool_csv}]")
        if self.mcp_servers:
            # Serialize MCP servers as a flow JSON dict — YAML accepts JSON
            # as a subset, the parser round-trips correctly through both.
            lines.append(f"mcp_servers: {json.dumps(self.mcp_servers, ensure_ascii=False)}")
        lines.append(f'description: "{esc(self.description.strip())}"')
        lines.append("---")
        frontmatter = "\n".join(lines) + "\n\n"
        body = self.body.strip() + "\n"
        return frontmatter + body


def _validate_spec(spec: AgentSpec) -> None:
    if not NAME_RE.fullmatch(spec.name):
        raise HTTPException(
            status_code=400,
            detail="Name must be lowercase, 3-64 chars, only letters/digits/dashes, no leading or trailing dash.",
        )
    if spec.model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Model must be one of: {', '.join(sorted(ALLOWED_MODELS))}",
        )
    if not spec.body.strip():
        raise HTTPException(status_code=400, detail="Body cannot be empty.")


def _to_dto(a: Agent, project: Project | None) -> AgentDTO:
    return AgentDTO(
        id=a.id,
        name=a.name,
        model=a.model,
        description=a.description,
        status=a.status,
        last_run_at=a.last_run_at.isoformat() if a.last_run_at else None,
        project_id=a.project_id,
        project_slug=project.slug if project else None,
        project_name=project.name if project else None,
        project_color=project.color if project else None,
        project_icon=project.icon if project else None,
        tools=list(a.tools) if a.tools else None,
        mcp_servers=dict(a.mcp_servers) if a.mcp_servers else None,
    )


async def _load_with_project(session, agent_id: int) -> tuple[Agent, Project | None] | None:
    a = (await session.execute(
        select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.project))
    )).scalar_one_or_none()
    if a is None:
        return None
    return a, a.project


@router.get("", response_model=list[AgentDTO])
async def list_agents(project: str | None = None) -> list[AgentDTO]:
    """List agents. If `project=<slug-or-id>` filter, only that project's team."""
    async with async_session_factory() as session:
        stmt = select(Agent).options(selectinload(Agent.project)).order_by(Agent.name)
        if project:
            try:
                pid = int(project)
                stmt = stmt.where(Agent.project_id == pid)
            except ValueError:
                proj = (await session.execute(
                    select(Project).where(Project.slug == project.lower())
                )).scalar_one_or_none()
                if proj is None:
                    return []
                stmt = stmt.where(Agent.project_id == proj.id)
        rows = (await session.execute(stmt)).scalars().all()
        return [_to_dto(a, a.project) for a in rows]


@router.get("/{agent_id}", response_model=AgentDTO)
async def get_agent(agent_id: int) -> AgentDTO:
    async with async_session_factory() as session:
        loaded = await _load_with_project(session, agent_id)
        if loaded is None:
            raise HTTPException(status_code=404, detail="agent not found")
        a, p = loaded
        return _to_dto(a, p)


_TASK_TYPE_TO_MODEL = {
    "fast": "claude-haiku-4-5-20251001",
    "deep": "claude-opus-4-7",
}


@router.post("/{agent_id}/run", status_code=202)
async def run_now(agent_id: int, body: RunNowBody) -> dict:
    async with async_session_factory() as session:
        a = await session.get(Agent, agent_id)
        if a is None:
            raise HTTPException(status_code=404, detail="agent not found")
        agent_name = a.name

    model_override = _TASK_TYPE_TO_MODEL.get((body.task_type or "").lower())
    run_id = await get_orchestrator().enqueue(RunRequest(
        agent_name=agent_name,
        prompt=body.prompt,
        source="dashboard",
        session_id=body.session_id,
        model_override=model_override,
        seek_devils_advocate=body.seek_devils_advocate,
    ))
    return {"run_id": run_id, "status": "queued"}


@router.post("", status_code=201, response_model=AgentDTO)
async def create_agent(body: AgentSpec) -> AgentDTO:
    """Create a new agent by writing its .md to the configured AGENTS_DIR.

    The watcher then upserts it into the DB. We also call upsert directly so
    the response carries the persisted row (no race with the filesystem event).
    """
    _validate_spec(body)
    agents_dir = runtime_state.agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    target = agents_dir / f"{body.name}.md"
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Agent file already exists: {target.name}")

    target.write_text(body.to_markdown(), encoding="utf-8")
    await upsert_agent_file(target)

    async with async_session_factory() as session:
        a = (await session.execute(
            select(Agent).where(Agent.name == body.name).options(selectinload(Agent.project))
        )).scalar_one_or_none()
        if a is None:
            raise HTTPException(status_code=500, detail="Agent registered but not visible yet.")
        await bus.publish("agent:registered", {"name": a.name, "via": "dashboard"})
        return _to_dto(a, a.project)


@router.get("/{agent_id}/source")
async def get_agent_source(agent_id: int) -> dict:
    """Return the editable spec for the agent (frontmatter fields + body)."""
    async with async_session_factory() as session:
        loaded = await _load_with_project(session, agent_id)
        if loaded is None:
            raise HTTPException(status_code=404, detail="agent not found")
        a, p = loaded
        return {
            "id": a.id,
            "name": a.name,
            "model": a.model,
            "description": a.description,
            "body": a.body,
            "source_path": a.source_path,
            "project_slug": p.slug if p else None,
            "project_name": p.name if p else None,
            "tools": list(a.tools) if a.tools else None,
            "mcp_servers": dict(a.mcp_servers) if a.mcp_servers else None,
        }


@router.put("/{agent_id}")
async def update_agent(agent_id: int, body: AgentSpec) -> AgentDTO:
    """Rewrite the agent's `.md` file. Renames are not allowed in this endpoint."""
    _validate_spec(body)
    async with async_session_factory() as session:
        a = await session.get(Agent, agent_id)
        if a is None:
            raise HTTPException(status_code=404, detail="agent not found")
        if a.name != body.name:
            raise HTTPException(
                status_code=400,
                detail="Renaming an agent is not supported here — delete the old file and create a new one.",
            )
        path = Path(a.source_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.to_markdown(), encoding="utf-8")
    await upsert_agent_file(path)

    async with async_session_factory() as session:
        loaded = await _load_with_project(session, agent_id)
        a, p = loaded  # type: ignore[misc]
        return _to_dto(a, p)


@router.post("/{agent_id}/move", response_model=AgentDTO)
async def move_agent(agent_id: int, body: dict) -> AgentDTO:
    """Reassign an agent to a different project (rewrites the .md frontmatter)."""
    target_slug = str(body.get("project_slug") or "").strip().lower() or "workspace"
    async with async_session_factory() as session:
        a = await session.get(Agent, agent_id)
        if a is None:
            raise HTTPException(status_code=404, detail="agent not found")
        proj = (await session.execute(
            select(Project).where(Project.slug == target_slug)
        )).scalar_one_or_none()
        if proj is None:
            raise HTTPException(status_code=404, detail=f"project not found: {target_slug}")
        path = Path(a.source_path)
        spec = AgentSpec(
            name=a.name,
            model=a.model,
            description=a.description,
            body=a.body,
            project_slug=target_slug,
            tools=list(a.tools) if a.tools else None,
            mcp_servers=dict(a.mcp_servers) if a.mcp_servers else None,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.to_markdown(), encoding="utf-8")
    await upsert_agent_file(path)

    async with async_session_factory() as session:
        loaded = await _load_with_project(session, agent_id)
        a, p = loaded  # type: ignore[misc]
        return _to_dto(a, p)


@router.post("/{agent_id}/mcp/{name}/test")
async def test_agent_mcp(agent_id: int, name: str) -> dict:
    """Spawn the configured MCP server and verify it answers the JSON-RPC handshake.

    Returns a structured result the UI can render:
    - ok=True with `tools` list when the server responded to tools/list.
    - ok=False with `error` + `error_kind` + `stderr_tail` when it failed.

    This is the most-asked-for v0.6 feature: before this, the only way to know
    if a configured MCP actually worked was to invoke the agent and watch logs.
    """
    async with async_session_factory() as session:
        a = await session.get(Agent, agent_id)
        if a is None:
            raise HTTPException(status_code=404, detail="agent not found")
        mcp_servers = a.mcp_servers or {}

    cfg = mcp_servers.get(name)
    if not cfg:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server '{name}' is not configured on this agent.",
        )

    # Accept both stdio (command/args/env) and pre-built dict shapes.
    command = cfg.get("command")
    args = cfg.get("args") or []
    env = cfg.get("env") or {}
    if not command:
        return {
            "ok": False,
            "error_kind": "bad_response",
            "error": "El MCP no tiene `command` configurado. Solo se pueden testear servers stdio.",
            "tools": [],
            "duration_ms": 0,
        }

    result = await test_mcp_server(command=command, args=args, env=env)
    return result.as_dict()


@router.get("/{agent_id}/runs")
async def list_runs(agent_id: int, limit: int = 50) -> list[dict]:
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Run).where(Run.agent_id == agent_id).order_by(desc(Run.id)).limit(limit)
        )).scalars().all()
        return [
            {
                "id": r.id,
                "source": r.source,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
                "prompt": r.prompt[:200],
                "error_message": r.error_message,
            }
            for r in rows
        ]
