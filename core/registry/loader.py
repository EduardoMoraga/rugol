"""Parse `.md` files with frontmatter into Agent/Skill records."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from core import llm_models


@dataclass
class ParsedAgent:
    name: str
    model: str
    description: str
    body: str
    body_hash: str
    source_path: str
    project_slug: str | None = None  # ADR-005; None → loader assigns to Workspace
    tools: list[str] | None = None    # Capa 5; None or [] → full preset
    mcp_servers: dict | None = None   # Capa 8; per-agent MCP server configs


@dataclass
class ParsedSkill:
    name: str
    description: str
    body: str
    body_hash: str
    source_path: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_agent_file(path: Path, default_model: str = llm_models.SONNET) -> ParsedAgent:
    """Parse an agent markdown file. Frontmatter must include `name`.

    Optional `project:` (ADR-005) attaches the agent to a project by slug.
    Unknown slugs are not auto-created; the upsert layer falls back to
    Workspace and logs a warning.
    """
    post = frontmatter.load(path)
    meta = post.metadata
    name = str(meta.get("name") or path.stem).strip()
    model = str(meta.get("model") or default_model).strip()
    description = str(meta.get("description") or "").strip()
    raw_project = meta.get("project")
    project_slug = str(raw_project).strip().lower() if raw_project else None
    raw_tools = meta.get("tools")
    tools: list[str] | None = None
    if isinstance(raw_tools, list):
        tools = [str(t).strip() for t in raw_tools if str(t).strip()]
        if not tools:
            tools = None
    elif isinstance(raw_tools, str) and raw_tools.strip():
        # Tolerate `tools: Read, Grep, Bash` written as a CSV string.
        tools = [t.strip() for t in raw_tools.split(",") if t.strip()]
    raw_mcp = meta.get("mcp_servers")
    mcp_servers: dict | None = raw_mcp if isinstance(raw_mcp, dict) and raw_mcp else None
    body = post.content
    return ParsedAgent(
        name=name,
        model=model,
        description=description,
        body=body,
        body_hash=_hash(body),
        source_path=str(path.resolve()),
        project_slug=project_slug,
        tools=tools,
        mcp_servers=mcp_servers,
    )


def load_skill_file(path: Path) -> ParsedSkill:
    """Parse a skill markdown file. Frontmatter may include `description`."""
    post = frontmatter.load(path)
    meta = post.metadata
    name = str(meta.get("name") or path.stem).strip()
    description = str(meta.get("description") or "").strip()
    body = post.content
    return ParsedSkill(
        name=name,
        description=description,
        body=body,
        body_hash=_hash(body),
        source_path=str(path.resolve()),
    )
