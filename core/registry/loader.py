"""Parse `.md` files with frontmatter into Agent/Skill records."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import frontmatter


@dataclass
class ParsedAgent:
    name: str
    model: str
    description: str
    body: str
    body_hash: str
    source_path: str


@dataclass
class ParsedSkill:
    name: str
    description: str
    body: str
    body_hash: str
    source_path: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_agent_file(path: Path, default_model: str = "claude-sonnet-4-6") -> ParsedAgent:
    """Parse an agent markdown file. Frontmatter must include `name`."""
    post = frontmatter.load(path)
    meta = post.metadata
    name = str(meta.get("name") or path.stem).strip()
    model = str(meta.get("model") or default_model).strip()
    description = str(meta.get("description") or "").strip()
    body = post.content
    return ParsedAgent(
        name=name,
        model=model,
        description=description,
        body=body,
        body_hash=_hash(body),
        source_path=str(path.resolve()),
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
