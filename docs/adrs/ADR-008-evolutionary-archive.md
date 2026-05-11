# ADR-008 — Soul-3 Evolutionary Archive (skeleton)

**Status:** Draft · 2026-05-10 · Authors: Eduardo Moraga + Claude (Opus 4.7)
**Implementation status:** **Not implemented.** Design only. Depends on
Soul-1 (ADR-006) shipped and Soul-2 (ADR-007) at least classifier-stable.

## Context

The Darwin Gödel Machine paper (Zhang/Hu/Lu/Lange/Clune, arXiv:2505.22954)
demonstrates that a self-modifying coding agent can climb SWE-bench from
20% to 50% by maintaining an **archive of agent versions**, sampling from
that archive, mutating via an LLM, and validating each mutation against
benchmarks. Crucially the archive is open-ended — branches that look
worse on the current benchmark are kept around because they may be
stepping stones to qualitatively new strategies later.

Rogologo today has a reflector (`core/improvements/reflector.py`) that
proposes a single mutation to the agent's body after a configurable
number of runs. The mutation is shown to the user as a diff; the user
accepts or rejects. This is a **linear loop**: one current version,
one proposal, accept/reject. No archive, no branches, no validation
beyond the human eye.

This ADR ports DGM-style open-ended evolution to Rogologo. The unit of
evolution is the **agent's system prompt** (its `body`), not its
Python code — that's the right surface for an LLM-driven product, and
it sidesteps the danger of an agent rewriting its own infrastructure.

## Decision (when implemented)

Each agent gains an **evolutionary archive**:

```
agent-soul/<agent_name>/
├── lineage.json              # tree of versions: id, parent_id, created_at, status
└── versions/
    ├── 001-initial.md        # the original .md template body
    ├── 002-tighter-tone.md   # proposed mutation
    ├── 003-add-pre-flight.md # proposed mutation
    └── ...
```

`lineage.json` carries per-version metrics aggregated from runs:

```json
{
  "current": "002",
  "versions": [
    {
      "id": "001",
      "parent": null,
      "created_at": "2026-05-01T00:00:00Z",
      "status": "archived",
      "metrics": {
        "runs": 47,
        "avg_cost_usd": 0.041,
        "avg_latency_ms": 4200,
        "thumbs_up_pct": 0.62,
        "user_corrections_per_run": 0.18
      }
    },
    {
      "id": "002",
      "parent": "001",
      "created_at": "2026-05-08T18:00:00Z",
      "status": "active",
      "metrics": { "...": "..." }
    }
  ]
}
```

### Mutation generator

The existing `reflector.py` is repurposed as the **mutation proposer**.
It receives the current version + a sample of recent runs (good and
bad) and produces 1-3 candidate mutations, each with a rationale and a
hypothesis (e.g. "removing the 'always quote sources' line should
shorten Telegram replies without hurting trust").

### Validator

For each candidate mutation, the validator replays a **golden set** of
historical prompts and compares the candidate's responses against:

1. **Cost / latency** — automatic, cheap.
2. **Self-critique** — Opus reads (original_prompt, old_response,
   new_response) and scores which is better with a structured rubric.
3. **User memory** — does the candidate violate any `feedback` memories
   the agent has? (E.g. a candidate that adds emoji to an agent with a
   "user prefers no emoji" feedback memory is auto-rejected.)

The result is a **fitness score** per candidate. Candidates above a
threshold are promoted to "ready to ship"; below threshold they're
archived but kept (DGM open-endedness — stepping stones).

### Branching and A/B

- A branch happens when two candidates score similarly. Both stay
  active; new runs are A/B-routed. After a configurable sample size
  (e.g. 30 runs each), the higher-scoring branch becomes default.
- Human override always wins. The dashboard shows the archive as a
  tree (react-flow, already in the stack for ontology); clicking any
  node sets that version as `current`.
- Rollback is one click: `current → parent_id`.

### Mutation cadence

- Triggered by `is_due` (already exists) — N runs since last mutation.
- Triggered manually from `/rogologo-self-improve <agent>`.
- Triggered automatically by **regression**: if avg_cost or
  thumbs_down_pct degrades sharply, propose a rollback candidate
  immediately.

## Tradeoffs

### Positive

- The "feeling" the user is paying for: agents that demonstrably get
  better month over month, with visible evidence (the tree, the
  metrics).
- Open-endedness: a branch that looks bad today may be useful when the
  agent's role shifts. Nothing gets deleted.
- Auditable: every system prompt the agent ever ran with is on disk,
  with parent links and rationale.
- DGM-aligned: this is the published recipe, ported to a different
  unit of evolution.

### Negative

- Validation cost. Replaying a golden set on Opus costs real money.
  Mitigation: rate-limit mutation proposals (default: weekly), use
  Haiku for the cheap parts of validation, keep golden sets small
  (10-20 prompts).
- Drift. An agent that mutates aggressively can lose touch with its
  original purpose. Mitigation: the **identity block** in Soul-1 is
  built from immutable fields (`name`, `description`) plus memory.
  Mutations only touch `body` and only land if they don't contradict
  `feedback` memories.
- Storage. Versions accumulate. Mitigation: archived versions older
  than N months get compressed into a single "ancestor" summary line.

## Implementation surface (when built)

New files:
- `core/soul/evolution/archive.py` — lineage.json read/write, file ops.
- `core/soul/evolution/proposer.py` — mutation generator (extends
  the existing `improvements/reflector.py`).
- `core/soul/evolution/validator.py` — golden-set replay + scoring.
- `core/soul/evolution/router.py` — A/B routing for active branches.
- `core/api/evolution.py` — REST endpoints for the dashboard.

Modified:
- `core/db/models.py` — `Run` row gains `agent_version_id: str | None`
  for telemetry.
- `core/runner/orchestrator.py` — when an agent has active branches,
  ask `router` which version to load before running.
- `dashboard/src/app/agents/[id]/evolution/page.tsx` — tree view.

## Open questions

- Format of the "golden set" — curated by humans, or auto-extracted
  from past runs that received explicit positive feedback?
- How to seed the archive when a new agent is registered — single
  version with the .md body, or pre-mutate to N candidates to bootstrap
  diversity?
- Cross-agent evolution: if agent A discovers a useful pattern, can the
  proposer suggest it to agent B? This is open-endedness across the
  fleet, not just within one agent. Probably yes, gated by similar
  agent description.

## Decision deferred until

Soul-1 has accumulated ≥100 real runs across ≥3 agents and Soul-2 (the
dispatcher) has stable telemetry. Without baseline metrics, the
validator can't score fitness.
