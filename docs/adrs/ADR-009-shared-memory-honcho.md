# ADR-009 — Shared cross-agent memory via Honcho

**Status:** Accepted · 2026-05-19 · Authors: Eduardo Moraga + Claude (Opus 4.7)

## Context

ADR-006 gave every agent a **private** memory store: each agent writes to
its own folder under `data/memory/<agent>/`, the runner injects that
agent's memories at the top of the system prompt, and ADR-007's dispatcher
adds Soul-1.5 auto-checkpoints so the file grows even when the agent
forgets to call `save_memory` itself.

That solves "agent A remembers what agent A learned". It does not solve
"the whole fleet learns about the same external peer". When several
agents in the same Rugol instance work for the same human — a morning
brief, an inbox triage, a narrative writer, a slide designer — every one
of them re-discovers basic facts about that human on its first encounter.
A user typing "I prefer chilean Spanish" to one agent does not change
anything for the next.

We need a layer where observations about external peers (users, clients,
teammates) are **shared** across agents, queryable in natural language,
and stored outside the local SQLite — so the knowledge survives a Docker
rebuild and is consultable from any future agent the user installs.

## Decision

Add an optional integration with **Honcho** (Plastic Labs,
[honcho.dev](https://honcho.dev)) as Rugol's shared cross-agent memory
backend. The integration ships as a single in-process MCP server,
`rugol-honcho`, that exposes three tools to any agent that lists it in
`mcp_servers`:

| Tool | Purpose |
|------|---------|
| `save_memory(content, peer_id, session_id?)` | Attribute an observation to a peer in a session. |
| `query_memory(query, peer_id)` | Ask Honcho a natural-language question; returns a synthesised answer over all observations about that peer. |
| `search_memory(query, limit?, session_id?)` | Semantic search across raw observations — for when the agent needs verbatim wording, not a summary. |

The MCP server is built lazily by the runner only when the calling agent
declares `rugol-honcho` in its `mcp_servers` map. The adapter
(`core/adapters/honcho.py`) imports the `honcho-ai` SDK lazily on first
use so a Rugol instance with `HONCHO_ENABLED=false` (the default) pays
zero cost — no extra dependency loaded, no network call, no surface area
exposed.

## Why both Soul and Honcho

The two layers solve adjacent problems and we keep them separate on
purpose. The line is:

| Concern | Soul Layer (ADR-006) | Honcho (this ADR) |
|---------|----------------------|-------------------|
| Scope | One agent | Whole fleet |
| Subject | "What I, agent X, learned" | "What we, all agents, know about peer P" |
| Storage | Local disk, version-controlled | Plastic Labs cloud, multi-tenant |
| Offline | Yes | No |
| Synthesis | Verbatim file injected in prompt | Honcho returns natural-language synthesis |
| Privacy | Stays on the user's machine | Leaves the machine — opt-in is mandatory |
| Default | Always on | Off |

An agent's private style, role, and per-project lessons stay in Soul. A
shared belief about an external peer goes to Honcho. When an agent needs
both, it calls both — the system prompt already carries the Soul block
and the tool calls are independent.

## Configuration surface

Five settings, all under the `HONCHO_*` prefix:

- `HONCHO_ENABLED` — master switch, default `false`.
- `HONCHO_API_KEY` — required when enabled. Loaded from `.env` only.
- `HONCHO_WORKSPACE_ID` — defaults to `rugol-default` so two
  installations do not silently share data.
- `HONCHO_ENVIRONMENT` — defaults to `production`. Set to a Honcho dev
  environment for testing.
- `HONCHO_DEFAULT_SESSION` — empty by default; the adapter then uses
  today's ISO date so observations are naturally grouped per day. Override
  for stable cross-day sessions.

The wizard never asks for a Honcho key. A user who wants the feature
sets `HONCHO_ENABLED=true` and the key in `.env` manually. This keeps the
first-run experience zero-surprise: no cloud signup gate.

## Failure modes

- **Feature disabled, agent calls a tool.** Tool returns an `is_error`
  payload with a one-line "Set HONCHO_ENABLED=true …" hint. The run does
  not crash.
- **Feature enabled, SDK not installed.** `honcho-ai` is listed in
  `requirements.txt` so a fresh `pip install -r` covers it, but
  hand-edited venvs survive: the tool returns a hint with the exact
  `pip install honcho-ai` command.
- **Network down.** Each tool call raises through the SDK; the catch-all
  in `honcho_tools.py` returns the exception text as an error payload.
  The agent decides how to recover (usually by falling back to Soul).
- **SDK signature changes.** `search_raw` probes for `session.search()`
  at runtime and falls back to `peer.chat()` with a search-style query
  when the method is absent. This guards against minor SDK drift without
  blocking releases on `honcho-ai` upgrades.

## Out of scope

- **Bundled agent updates.** No agent in `agents-templates/` will declare
  `rugol-honcho` in its `mcp_servers` until we have a recipe pattern
  proven on at least two real users. The first install ships with the
  capability available but nobody using it.
- **Multi-workspace routing.** A single Rugol instance points at a
  single Honcho workspace. Tenant-style routing is deferred.
- **Local fallback.** Honcho is intentionally cloud-only here. Users who
  want a local-only shared memory should stay on Soul or wait for an
  ontology-backed alternative (ADR-004).

## Consequences

- **Positive.** Agents can answer "what does the fleet know about X?"
  without a manual sync step. The user stops typing the same preference
  twice. Cross-agent context is built passively as each agent runs.
- **Negative.** First true external dependency that costs money and
  leaves the user's machine. Mitigated by the opt-in default and the
  workspace-isolation hint in the README.
- **Operational.** Future ADRs need to address (a) which bundled agents
  default-on Honcho, (b) how the dashboard surfaces "this run wrote to
  Honcho", and (c) whether Honcho can also store agent-to-agent
  observations, not just peer observations.

## References

- Honcho docs — https://honcho.dev/docs
- ADR-006 — Soul Layer (private per-agent memory)
- ADR-007 — Dual-track dispatcher
- ADR-008 — Evolutionary archive
