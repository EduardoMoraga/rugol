"""Per-agent persistent memory — file-based, simple, durable.

Same idea as Claude Code's auto-memory:
  agent-memory/
    <agent_name>/
      MEMORY.md          # short index, one line per file
      <slug>.md          # one memory per file with frontmatter

Each memory file has frontmatter (name, description, kind) and a body.
Before every run, the orchestrator reads the index for the agent and
appends a "## Agent memory" block to the system prompt.

Why files (not vector DB) — see docs/upgrade-v0.6.md, decision documented
in roadmap-v0.6.md Sprint G-decimal: until volumes hit hundreds of
memories per agent, file-based with description matching outperforms
embeddings on dev simplicity and the user's ability to inspect /
edit / version-control the memories.
"""
from core.memory.store import (
    Memory,
    add_memory,
    build_memory_block,
    delete_memory,
    list_memories,
    memory_dir,
)

__all__ = [
    "Memory",
    "add_memory",
    "build_memory_block",
    "delete_memory",
    "list_memories",
    "memory_dir",
]
