# ADR-006 — Soul Layer

**Status:** Accepted · 2026-05-10 · Authors: Eduardo Moraga + Claude (Opus 4.7)

## Context

Through v0.6 Rugol grew the plumbing for agentic operations: scheduling,
streaming, ontology, project context, and a per-agent file-based memory
store. The memory layer was already wired to **read** before every run
(`orchestrator.py` injects `build_memory_block` into the system prompt),
but it was missing two halves that turned out to matter more than the read
itself:

1. The agent could not **write** memory autonomously during a run. The
   `add_memory()` function existed but was reachable only from outside —
   Telegram `/remember`, the dashboard, or the REST API.
2. The agent had no **instructions** explaining when memory was worth
   keeping. Even with a write tool, an agent without a policy never knows
   that "Eduardo prefers chileno" is a fact to persist while "Eduardo just
   said hello" is not.

The user surfaced this at a run-time level: an agent answered
"I should have been saving memory all week without you asking" — which was
literally true. The platform had built the museum but never given the
inhabitants the ability to write on the walls.

This ADR commits to a **Soul Layer**: a stack of capabilities every agent
inherits the moment it is registered. The name is intentional. The bet is
that what users actually want from an agent platform is not a fancier
runner — it is the feeling that the agent remembers them, sounds like
itself, gets better, and reflects.

The architectural inspiration is two-fold:

- **Darwin Gödel Machine (Zhang/Hu/Lu/Lange/Clune, arXiv:2505.22954)** —
  an open-ended self-improving agent that mutates its own code, validates
  empirically against benchmarks, and grows an evolutionary archive. Soul-3
  ports this concept to the system prompt of every Rugol agent.
- **Kahneman's dual-process theory (Thinking, Fast and Slow)** — System 1
  is fast, intuitive, cheap; System 2 is slow, deliberate, expensive. Soul-2
  applies this to model routing: trivial requests go to a Haiku pipeline
  with cached context; complex requests go to an Opus plan-then-execute
  pipeline.

## Decision

Rugol gains a `core/soul/` module with four sub-capabilities, delivered
across three sprints. Sprint 1 ships in this ADR; Sprints 2 and 3 are
documented in ADR-007 and ADR-008 as design skeletons before
implementation.

### Soul-1 — Proactive memory (this sprint)

Every run is bracketed by three new pieces of behaviour:

1. **Identity block** — prepended to the system prompt. Renders the
   agent's name, description, and a short relationship summary
   ("you have run 47 times for Eduardo; he prefers chileno phrasing;
    last meaningful interaction was about Versuni Q2 budget").
   The block is built from the existing `agents` row plus the
   per-agent memory index. No new schema.
2. **Auto-memory rules block** — appended to the system prompt. A
   concise policy document the agent reads on every run: when to save
   memory, what four kinds to use (user/feedback/project/reference),
   what NOT to save, how to update vs duplicate. Modelled on the
   `# auto memory` block Anthropic ships in Claude Code itself.
3. **`save_memory` / `list_my_memories` / `forget_memory` tools** —
   exposed as an in-process MCP server `rugol-soul` using
   `claude_agent_sdk.create_sdk_mcp_server`. The tools wrap the
   existing `core.memory` store. The server is constructed fresh for
   each run with the agent's name captured in closure, so cross-agent
   contamination is impossible.

### Soul-2 — Dual-track dispatcher (ADR-007, future sprint)

Before invoking the model, route the request through a classifier that
labels it S1 (intuitive) or S2 (deliberate). S1 goes to Haiku with
prompt caching enabled; S2 goes to Opus with a plan-then-execute
wrapper. Soul-3 is partially in place (`model_override`) but lacks the
classifier and the cache layer.

### Soul-3 — Evolutionary archive (ADR-008, future sprint)

Port DGM to system prompts: each agent has a linage of system-prompt
versions, each version tagged with run-level metrics (cost, satisfaction,
task completion). The reflector proposes mutations; the validator runs
the candidate against a sample of historical prompts; a human (or, later,
an A/B win-rate) decides which version becomes default. Branching is
allowed — multiple lineages can coexist.

## Consequences

### Positive

- Cross-cutting feature: any agent registered in Rugol inherits
  memory + identity without extra config.
- Closes the "I should have been saving memory" gap permanently.
- Hookable: anything that wants to listen on `memory:added` can do so
  via the existing bus.
- Backwards compatible: agents that already have memory keep it; the
  new tools simply expand what the agent can do on its own.

### Negative

- ~600-1500 additional tokens in the system prompt per run. On Haiku
  these are cents; on Opus they're real money. Soul-2 (dual-track)
  exists partly to amortize this — Haiku S1 runs eat the prompt cheap.
- A misbehaving agent could now save thousands of useless memories.
  Mitigation: the auto-memory rules block is explicit about NOT
  saving derivable / ephemeral / debug-recipe content, and the
  dashboard has list/edit/delete affordances.
- Identity drift is possible if reflection rewrites the identity block.
  Mitigation: identity is built from the **immutable** name + description
  fields plus the memory index; reflection writes to memory, not to the
  description.

### Out of scope for Sprint 1

- The dual-track classifier (Soul-2).
- The DGM archive and branching (Soul-3).
- Per-agent ontology projections (today the ontology is global).

## Implementation surface

New files:
- `core/soul/__init__.py`
- `core/soul/identity.py` — `build_identity_block(agent) -> str`
- `core/soul/auto_memory.py` — constant `AUTO_MEMORY_RULES` rendered block
- `core/soul/tools.py` — `build_soul_mcp_server(agent_name) -> McpSdkServerConfig`
- `core/soul/builder.py` — `build_soul_context(agent) -> str` (composes 1+2+3)
- `tests/test_soul.py` — unit + end-to-end coverage

Modified:
- `core/runner/orchestrator.py` — calls `build_soul_context`, passes it
  and the agent name to the runner.
- `core/runner/claude_runner.py` — accepts `soul_context: str | None` and
  `soul_mcp_server: McpSdkServerConfig | None`; merges into the system
  prompt and MCP server map; allow-lists the three soul tools.

No schema changes. No new dependencies (MCP is already in the SDK).
