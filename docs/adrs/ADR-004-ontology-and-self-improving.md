# ADR-004 — Ontology graph and self-improving loop

**Status:** Accepted · 2026-05-02 · Author: rugol-architect

## Context

Two ideas the user pointed at directly:

1. **Ontology** ([oswalpalash/ontology](https://clawhub.ai/oswalpalash/ontology)):
   a structured shared memory that agents read from and write to, so they stop
   re-discovering the same facts every run.
2. **Self-improving** ([pskoett/self-improving-agent](https://clawhub.ai/pskoett/self-improving-agent)):
   an agent that, after each run, reflects on its outcome and proposes edits
   to its own spec.

Both are powerful and both are commonly implemented poorly — too magical, too
unbounded, too easy to corrupt. Our job is to add them with strict guardrails.

## Decision

### Ontology

A SQLite **triple store** (subject-predicate-object) lives in the same DB as
the rest of the app. Two tables: `ontology_nodes` and `ontology_edges` (see
`ARCHITECTURE.md` §3).

- Agents **read** via a `MemoryRead` tool that exposes a small query API
  (`neighbors`, `find_by_label`, `path`).
- Agents **write** via a `MemoryWrite` tool that takes a typed payload —
  free-form prose is rejected. Each write records the originating `run_id`,
  giving us full provenance.
- A small in-process cache speeds up repeat reads inside a single run.
- The dashboard ships a `react-flow` viewer of the graph for inspection &
  manual edits (humans can curate).

Out of scope for v1: embedding-based fuzzy retrieval. v2 adds a vector
column on `ontology_nodes` and a `MemorySearch` tool.

### Self-improving

After a run completes, the **improver** decides whether to spawn a reflection
job:

```python
def is_due(agent_id: str) -> bool:
    last_n = recent_runs(agent_id, n=10)
    if any(r.failed for r in last_n[-3:]):
        return True                 # 3 fails → reflect
    if not improvements.has_open_proposal(agent_id):
        return last_n.count >= 10   # every 10 runs, reflect
    return False
```

The reflection job calls Claude with a fixed meta-prompt:

```
You are reviewing your own performance. Below is your current spec, then
the prompts and outcomes of your last K runs. Propose precise, surgical
edits to your .md (unified diff format) that would improve future runs.
Constraints:
- Do not invent new tools you do not have.
- Do not change your name or model.
- Keep the diff under 30 lines.
- Justify each change in 1 sentence.
```

Output is parsed and persisted as a row in `improvements` (status=`proposed`).
The dashboard surfaces a notification. **The agent's `.md` is never modified
without explicit human approval.**

## Consequences

- **Positive:** Agents accumulate institutional knowledge; ontology lookups
  cut tokens spent re-explaining the world.
- **Positive:** Self-improvement is a delight feature with a kill-switch:
  every change is reviewable, revertable, attributable.
- **Negative:** Ontology drift is a real risk if many agents write
  contradictory facts. We mitigate with predicate vocabularies and a
  weekly "ontology audit" run we ship as a built-in skill.
- **Negative:** The reflection prompt costs tokens. We cap to one
  reflection per agent per day to keep cost predictable.

## Alternatives rejected

- **MemGPT-style hierarchical memory**: powerful but adds substantial state
  machinery; v2 candidate.
- **Pinecone or Weaviate vector DB**: external dependency, breaks the
  "single docker compose up" promise. Local FAISS or sqlite-vss is the
  v2 path.
- **Auto-applied self-edits**: rejected outright on safety grounds.
- **Per-run reflection (every run)**: too expensive; cap to threshold-based.
