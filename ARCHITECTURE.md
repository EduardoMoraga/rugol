# Rugol — Architecture

> Audience: contributors, reviewers, and Anthropic engineers reading the repo
> for the first time. Read this once and you will know where every byte lives.

## 1. Bird's-eye view

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            User-facing surfaces                              │
│                                                                              │
│  Browser            Telegram             Slack            CLI                │
│   ▲                   ▲                    ▲               ▲                 │
│   │ HTTP+SSE          │ long-poll          │ events API    │ rugol …      │
│   ▼                   ▼                    ▼               ▼                 │
│ ┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────────┐         │
│ │ Next.js  │    │ Telegram     │    │ Slack       │    │ Click CLI │         │
│ │ Dashboard│    │ Adapter      │    │ Adapter     │    │ (Python)  │         │
│ │ (port    │    │ (asyncio)    │    │ (Bolt SDK)  │    │           │         │
│ │  3000)   │    └──────┬───────┘    └──────┬──────┘    └─────┬─────┘         │
│ └────┬─────┘           │                   │                 │               │
│      │ /api/*          │                   │                 │               │
│      └─────────────────┴────────┬──────────┴─────────────────┘               │
│                                 ▼                                            │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │                         FastAPI Core (port 8000)                         │ │
│ │                                                                          │ │
│ │  ┌─────────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────────┐     │ │
│ │  │ REST        │  │ SSE      │  │ Webhooks   │  │ MCP server stub  │     │ │
│ │  │ /api/*      │  │ /stream  │  │ /webhooks/*│  │ (future)         │     │ │
│ │  └──────┬──────┘  └────┬─────┘  └─────┬──────┘  └──────────────────┘     │ │
│ │         └──────────────┴──────────────┘                                  │ │
│ │                            │                                             │ │
│ │  ┌─────────────────────────┴─────────────────────────────────────────┐   │ │
│ │  │                       RuntimeOrchestrator                         │   │ │
│ │  │   • registry (load .md agents/skills, hot-reload)                 │   │ │
│ │  │   • scheduler (APScheduler: cron + interval + one-shot)           │   │ │
│ │  │   • runner   (spawns claude-agent-sdk subprocesses)               │   │ │
│ │  │   • bus      (in-process pub/sub → SSE → dashboard)               │   │ │
│ │  │   • limiter  (semaphore on MAX_CONCURRENT_RUNS)                   │   │ │
│ │  │   • ontology (memory graph: subject-predicate-object)             │   │ │
│ │  │   • improver (post-run reflection loop)                           │   │ │
│ │  └────────────────────────────┬──────────────────────────────────────┘   │ │
│ │                               │                                          │ │
│ │           ┌───────────────────┼─────────────────────────┐                │ │
│ │           ▼                   ▼                         ▼                │ │
│ │    ┌─────────────┐    ┌──────────────┐         ┌─────────────────┐       │ │
│ │    │ SQLite/PG   │    │ Redis (opt)  │         │ Filesystem      │       │ │
│ │    │ • runs      │    │ • run queue  │         │ • agents/*.md   │       │ │
│ │    │ • agents    │    │ • SSE fanout │         │ • skills/*.md   │       │ │
│ │    │ • schedules │    │              │         │ • memory/       │       │ │
│ │    │ • messages  │    └──────────────┘         │ • attachments/  │       │ │
│ │    │ • ontology  │                             │ • logs/         │       │ │
│ │    │ • costs     │                             └─────────────────┘       │ │
│ │    └─────────────┘                                                       │ │
│ └──────────────────────────────────┬───────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │                          claude CLI (subprocess)                         │ │
│ │      ─ uses subscription OAuth (default)  or  ANTHROPIC_API_KEY          │ │
│ │      ─ inherits .claude/agents/, .claude/skills/, MCP config             │ │
│ │      ─ outputs streamed JSON parsed by RuntimeOrchestrator               │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 2. Process model

A single Docker Compose project brings up four containers:

| Service | Image | Purpose |
|---------|-------|---------|
| `core` | python:3.12-slim + app | FastAPI + scheduler + adapters |
| `dashboard` | node:20 + Next.js | UI on port 3000 |
| `db` | postgres:16-alpine *(optional)* | Persistent storage if not using SQLite |
| `redis` | redis:7-alpine *(optional)* | Pub/sub fan-out for SSE in multi-replica setups |

The default profile is **single-host SQLite, no Redis** — perfect for a personal
PC. The `prod` profile turns on Postgres and Redis for shared deployments.

## 3. Data model (SQLite/Postgres)

```
agents
  id (pk)
  name (unique)
  model
  description
  source_path        -- /agents/brand-architect.md
  body_hash          -- sha256 of the file body, drives reload
  status             -- idle | running | error | offline
  last_run_at
  created_at, updated_at

skills
  id (pk)
  name (unique)
  description
  source_path
  body_hash

schedules
  id (pk)
  agent_id (fk → agents.id)
  cron_expr          -- e.g. "0 9 * * 1"  Mondays 9am
  prompt             -- the message to send each fire
  enabled
  next_run_at
  last_run_at
  created_at

runs
  id (pk)
  agent_id (fk)
  schedule_id (fk, nullable)
  source             -- schedule | telegram | slack | dashboard | api
  prompt
  started_at, ended_at
  status             -- running | completed | failed | cancelled
  exit_code
  input_tokens, output_tokens, cost_usd
  session_id         -- claude-agent-sdk session id, for resume
  error_message

messages
  id (pk)
  run_id (fk)
  role               -- user | assistant | tool | system
  content_md         -- markdown
  content_json       -- raw block (tool_use, etc.)
  ts

ontology_nodes
  id (pk)
  type               -- concept | entity | event
  label              -- "Versuni", "promotor", "OSA"
  meta_json
  created_at

ontology_edges
  id (pk)
  src (fk → ontology_nodes.id)
  predicate          -- "is_a", "owns", "related_to"
  dst (fk)
  weight
  created_by_run (fk → runs.id, nullable)
  created_at

improvements
  id (pk)
  agent_id (fk)
  proposed_diff_md
  rationale
  status             -- proposed | approved | rejected | applied
  proposed_by_run (fk)
  reviewed_by        -- user id (future multi-user)
  reviewed_at

channels
  id (pk)
  type               -- telegram | slack
  external_id        -- chat_id / channel_id
  team_name          -- group of agents bound to this channel
  bound_agent_ids    -- json array
```

## 4. Lifecycles

### 4.1 Agent discovery

```
filesystem watcher (watchdog) → debounce 200ms →
  parse frontmatter → upsert agents row → emit "agent:registered" on bus
```

If `body_hash` changes, the agent is reloaded but **active runs are not killed**;
the new body applies on the next run.

### 4.2 A run (schedule fires)

```
APScheduler fires job →
  RuntimeOrchestrator.enqueue(agent, prompt, source="schedule") →
  semaphore.acquire(MAX_CONCURRENT_RUNS) →
  fork claude-agent-sdk subprocess with cwd=workspace →
  stream parser:
    AssistantMessage   → bus.emit("run:message", run_id, content)
    ToolUseBlock       → bus.emit("run:tool",    run_id, name)
    ResultMessage      → persist tokens & cost, mark completed
  on exit:
    if status == completed and improver.is_due(agent): improver.schedule(run)
  semaphore.release()
```

The bus is in-process (`asyncio.Queue` per subscriber). SSE clients subscribe
via `/api/stream?topics=run:*`. In a multi-replica setup the bus delegates to
Redis pub/sub.

### 4.3 Inbound message (Telegram example)

```
Telegram long-poll → handle_message →
  resolve channel → if team mode: route by @mention or default agent
                   → if 1:1 mode: forward to bound agent
  RuntimeOrchestrator.enqueue(agent, message_text, source="telegram", ctx={chat_id})
  on completion: telegram_io.send_long(chat_id, response)
```

The Telegram adapter is a near-verbatim port of `eduagent-gateway/gateway.py`
with the runtime call changed to `RuntimeOrchestrator.enqueue` instead of
direct SDK invocation.

### 4.4 Self-improving cycle

```
on run:completed →
  improver.collect_signal(run)        -- last N runs of this agent
  if signal.score < threshold OR run.failed:
    improver.spawn(run.agent_id) →
      meta-prompt to claude:
        "Here is your current spec, the last K runs, and their outcomes.
         Propose precise edits to your own .md that would improve future runs.
         Output: a unified diff and a 2-sentence rationale."
      persist as improvements row (status=proposed)
      emit "improvement:proposed" on bus → dashboard notification
human reviews diff in dashboard →
  approve → atomic write the new file body, bump body_hash
  reject  → mark rejected, store reason
```

The agent never edits itself unsupervised. **Human-in-the-loop is mandatory.**

## 5. The ant-farm

The dashboard renders a `react-pixi` canvas where each agent is a sprite.

States and animations:

| State | Sprite | Behavior |
|-------|--------|----------|
| `idle` | gray ant, slow blink | wanders within its "tile" |
| `running` | green ant, antennae moving | walks toward "queen" task icon, carries cargo back |
| `error` | red ant, shaking | stays still, exclamation mark above |
| `offline` | gray, semi-transparent | crossed out |

Tile layout is a hex grid auto-laid by agent count (1 → center, 2-7 → ring,
8+ → spiral). Hovering a sprite shows live tooltip: last run, current task,
cost-this-week. Clicking jumps to the agent's detail panel.

This is **not** Stanford Smallville (we are not simulating relationships).
The ant-farm is an attention surface — it makes "30 agents are alive" tangible.

## 6. Ontology (memory graph)

The shared memory is a triple store. Any agent can read/write, but **writes
require a structured `MemoryWrite` tool call** (not free text) so the graph
stays clean.

```
[Versuni] ──is_a──→ [Cliente]
[Versuni] ──owns──→ [Promotor #234]
[Promotor #234] ──visited──→ [PDV Jumbo Ñuñoa] (ts=2026-04-30)
```

Queries: `ontology.neighbors("Versuni", predicate="owns")` returns all promoters.
The dashboard exposes a graph viewer (`react-flow`) for inspection.

Ontology is **local-first**: no external DB, no embeddings yet (v2 will add
a vector layer for fuzzy retrieval).

## 7. Security model

- **No code paths handle plaintext secrets**; all reads go through `config.py`
  which loads from environment.
- **Telegram & Slack**: strict allowlist by user ID (Telegram) or workspace
  membership (Slack). Bots ignore messages from unknown senders.
- **claude CLI permissions**: the subprocess inherits `permission_mode="bypassPermissions"`
  because Rugol is the trusted operator; the CLI's safety lives at the
  agent level (each agent's `.md` declares what tools it may use).
- **Self-improving** never auto-applies edits — proposals queue in the
  dashboard for explicit approval.
- **Telemetry** is opt-in and anonymous; only event names + counts.

## 8. Performance targets (MVP)

| Metric | Target |
|--------|--------|
| Cold dashboard load | < 1.5 s (Lighthouse mobile) |
| SSE event end-to-end latency | < 200 ms p95 |
| Time from `claude` invocation to first token | < 4 s p50 |
| Concurrent runs on a 16 GB PC | 5 (subscription) / 20 (API) |
| File watcher reload | < 1 s after `.md` save |

## 9. What we explicitly do NOT do (yet)

- Multi-tenant cloud hosting (the design is single-host).
- LLMs other than Claude (the runner is Claude-shaped on purpose; pluggable in v2).
- Mobile-native apps (the dashboard is responsive, but PWA is the v2 path).
- Complex IAM (single-user assumed; future RBAC is a v2 ADR).

See [`docs/adrs/`](docs/adrs/) for the why behind every choice above.
