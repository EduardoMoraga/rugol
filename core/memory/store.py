"""File-based memory store per agent.

API
---
- memory_dir(agent_name) → Path        # repo_root/agent-memory/<name>/
- list_memories(agent_name) → list[Memory]
- add_memory(agent_name, name, description, content, kind="note") → Memory
- delete_memory(agent_name, name) → bool
- build_memory_block(agent_name, max_chars=4000) → str | None

Storage layout
--------------
agent-memory/<agent_name>/
  MEMORY.md           # plain index, one bullet per memory:
                      #   - [name](file.md) — description
  YYYYMMDD-slug.md    # one memory per file with frontmatter:
                      #   ---
                      #   name: short title
                      #   description: one-line hook (used in index)
                      #   kind: note|fact|preference|reference|episode
                      #   created_at: ISO8601
                      #   ---
                      #   <body>

The orchestrator reads MEMORY.md + the description fields and injects
the relevant memories into the system prompt before each run. Right now
"relevant" = "all of them", capped to max_chars; once volumes get bigger
we add semantic search (Sprint C of the memory roadmap).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    # core/memory/store.py → core → repo
    return Path(__file__).resolve().parent.parent.parent


def _slug(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "memory"


def memory_dir(agent_name: str) -> Path:
    safe = _slug(agent_name)
    return _repo_root() / "agent-memory" / safe


def _index_path(agent_name: str) -> Path:
    return memory_dir(agent_name) / "MEMORY.md"


@dataclass
class Memory:
    name: str
    description: str
    kind: str
    created_at: str
    body: str
    file: str  # filename (not full path) for relative refs

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "created_at": self.created_at,
            "body": self.body,
            "file": self.file,
        }


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n(.*)$", re.DOTALL)


def _parse_memory(path: Path) -> Memory | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("could not read memory %s: %s", path, e)
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm_block, body = m.group(1), m.group(2).strip()
    fm: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return Memory(
        name=fm.get("name", path.stem),
        description=fm.get("description", ""),
        kind=fm.get("kind", "note"),
        created_at=fm.get("created_at", ""),
        body=body,
        file=path.name,
    )


def list_memories(agent_name: str) -> list[Memory]:
    """Return all memories for an agent, sorted oldest → newest by created_at fallback to filename."""
    d = memory_dir(agent_name)
    if not d.exists():
        return []
    out: list[Memory] = []
    for p in sorted(d.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        mem = _parse_memory(p)
        if mem is not None:
            out.append(mem)
    out.sort(key=lambda m: (m.created_at or m.file))
    return out


def add_memory(
    agent_name: str,
    name: str,
    description: str,
    content: str,
    kind: str = "note",
) -> Memory:
    """Append a new memory file and update MEMORY.md."""
    d = memory_dir(agent_name)
    d.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    base = f"{now.strftime('%Y%m%d')}-{_slug(name)}"
    # Avoid collisions if same slug used twice in one day.
    out = d / f"{base}.md"
    suffix = 2
    while out.exists():
        out = d / f"{base}-{suffix}.md"
        suffix += 1
    desc_clean = description.replace("\n", " ").replace('"', "'")
    name_clean = name.replace("\n", " ").replace('"', "'")
    fm = (
        "---\n"
        f"name: {name_clean}\n"
        f"description: {desc_clean}\n"
        f"kind: {kind}\n"
        f"created_at: {now.isoformat()}\n"
        "---\n\n"
    )
    out.write_text(fm + content.strip() + "\n", encoding="utf-8")
    _rebuild_index(agent_name)
    logger.info("memory added for %s: %s", agent_name, out.name)
    return Memory(
        name=name_clean,
        description=desc_clean,
        kind=kind,
        created_at=now.isoformat(),
        body=content.strip(),
        file=out.name,
    )


def delete_memory(agent_name: str, file_or_name: str) -> bool:
    """Delete by exact filename or by `name` field. Returns True if found."""
    d = memory_dir(agent_name)
    if not d.exists():
        return False
    target = d / file_or_name
    if target.exists() and target.suffix == ".md":
        target.unlink()
        _rebuild_index(agent_name)
        return True
    # Fallback: search by name.
    for mem in list_memories(agent_name):
        if mem.name == file_or_name:
            (d / mem.file).unlink()
            _rebuild_index(agent_name)
            return True
    return False


def _rebuild_index(agent_name: str) -> None:
    """Rewrite MEMORY.md from the actual files. Idempotent."""
    d = memory_dir(agent_name)
    if not d.exists():
        return
    mems = list_memories(agent_name)
    lines: list[str] = [f"# Memorias de {agent_name}", ""]
    if not mems:
        lines.append("(vacío — agrega memorias con /remember en Telegram, vía API, o desde el dashboard)")
    else:
        for m in mems:
            lines.append(f"- [{m.name}]({m.file}) — {m.description}")
    (d / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_memory_block(agent_name: str, max_chars: int = 4000) -> str | None:
    """Render the memories of an agent as a system-prompt block.

    Greedy: includes memories oldest-first up to max_chars. When the budget
    is exhausted, appends a count of how many were skipped so the model
    knows there's more.
    """
    mems = list_memories(agent_name)
    if not mems:
        return None
    out_lines: list[str] = ["## Tu memoria persistente (releída antes de cada run)"]
    used = len(out_lines[0])
    skipped = 0
    for m in mems:
        block = f"\n### {m.name}  [{m.kind}]\n{m.body.strip()}\n"
        if used + len(block) > max_chars:
            skipped += 1
            continue
        out_lines.append(block)
        used += len(block)
    if skipped:
        out_lines.append(f"\n_...y {skipped} memoria(s) más que no entraron por límite de tokens._")
    return "".join(out_lines).strip()
