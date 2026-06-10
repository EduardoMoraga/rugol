"""Memory graph builder — the Obsidian-style network behind /memory-graph.

Walks every agent's memory folder, extracts ``[[wikilinks]]`` from memory
bodies, and produces a nodes+edges payload the dashboard renders as a
force-directed graph (the agent's "neural network").

Node types
----------
- ``agent``    one per agent that has memories; hub of its own cluster.
- ``memory``   one per memory file; carries kind/description/body excerpt.
- ``concept``  a wikilink target that doesn't resolve to any memory — the
  emergent "concept cloud". Concepts are global, so two agents linking the
  same concept get visually connected through it (cross-agent knowledge).

Edge types
----------
- ``owns``  agent → memory (membership).
- ``link``  memory → memory | concept (a ``[[wikilink]]`` in the body).

Resolution order for a wikilink target: same-agent memory by ``name``,
same-agent by file stem, any-agent by ``name``, else a concept node.
"""
from __future__ import annotations

import re

from core.memory.store import list_memories, memory_dir

# [[target]] or [[target|alias]]; stop at | or # (Obsidian heading refs).
_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:[\|#][^\]]*)?\]\]")

_BODY_EXCERPT = 1500


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def extract_wikilinks(body: str) -> list[str]:
    """Unique wikilink targets in order of first appearance."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _WIKILINK_RE.finditer(body or ""):
        target = m.group(1).strip()
        key = _norm(target)
        if key and key not in seen:
            seen.add(key)
            out.append(target)
    return out


def build_memory_graph() -> dict:
    """Assemble the global graph across every agent with memories."""
    root = memory_dir("x").parent  # agent-memory/ root, agent-agnostic
    agents: list[str] = []
    if root.exists():
        agents = sorted(d.name for d in root.iterdir() if d.is_dir())

    nodes: list[dict] = []
    edges: list[dict] = []
    # Lookups for wikilink resolution.
    by_agent_name: dict[tuple[str, str], str] = {}   # (agent, norm-name) → node id
    by_agent_stem: dict[tuple[str, str], str] = {}   # (agent, file-stem) → node id
    by_global_name: dict[str, str] = {}              # norm-name → node id (first wins)
    memories: list[tuple[str, str, str]] = []        # (agent, node_id, body)

    for agent in agents:
        mems = list_memories(agent)
        if not mems:
            continue
        nodes.append({
            "id": f"a:{agent}",
            "type": "agent",
            "label": agent,
        })
        for m in mems:
            stem = m.file[:-3] if m.file.endswith(".md") else m.file
            nid = f"m:{agent}/{stem}"
            nodes.append({
                "id": nid,
                "type": "memory",
                "label": m.name,
                "agent": agent,
                "kind": m.kind or "note",
                "description": m.description,
                "file": m.file,
                "created_at": m.created_at,
                "body": m.body[:_BODY_EXCERPT],
            })
            edges.append({"source": f"a:{agent}", "target": nid, "type": "owns"})
            by_agent_name[(agent, _norm(m.name))] = nid
            by_agent_stem[(agent, stem)] = nid
            by_global_name.setdefault(_norm(m.name), nid)
            memories.append((agent, nid, m.body))

    # Second pass: resolve wikilinks now that every memory is indexed.
    concepts: dict[str, str] = {}  # norm-label → node id
    seen_edges: set[tuple[str, str]] = set()
    for agent, nid, body in memories:
        for target in extract_wikilinks(body):
            key = _norm(target)
            dst = (
                by_agent_name.get((agent, key))
                or by_agent_stem.get((agent, target.strip()))
                or by_global_name.get(key)
            )
            if dst is None:
                dst = concepts.get(key)
                if dst is None:
                    dst = f"c:{key}"
                    concepts[key] = dst
                    nodes.append({"id": dst, "type": "concept", "label": target.strip()})
            if dst == nid:
                continue  # self-link
            ekey = (nid, dst)
            if ekey in seen_edges:
                continue
            seen_edges.add(ekey)
            edges.append({"source": nid, "target": dst, "type": "link"})

    # Degree (for node sizing in the UI).
    degree: dict[str, int] = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    for n in nodes:
        n["degree"] = degree.get(n["id"], 0)

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "agents": sum(1 for n in nodes if n["type"] == "agent"),
            "memories": sum(1 for n in nodes if n["type"] == "memory"),
            "concepts": len(concepts),
            "links": sum(1 for e in edges if e["type"] == "link"),
        },
    }
