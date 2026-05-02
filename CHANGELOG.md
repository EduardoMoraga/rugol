# Changelog

All notable changes to Rogologo are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Sprint 3 — Real product (DONE, 2026-05-02)

The "navigable scaffold" feedback was correct. This release fixes the bugs,
gives Rogologo a real visual identity, and turns the dashboard into something
you actually *operate* the system from — not just look at.

**Fixed**
- `/agents/[id]` 500 ("Jest worker child process exception"): replaced the
  `params: Promise<>` + `use()` pattern with `useParams()`, which Turbopack
  handles cleanly.
- Ant farm hang: replaced the `react-pixi` WebGL implementation with a plain
  HTML5 Canvas renderer. No WebGL context loss, no pixi version drift, smaller
  bundle, smoother animation.
- Ontology page hang: `<ReactFlow>` was bootstrapping `fitView` against zero
  nodes and looping. Hard guard now renders an empty state until at least one
  node exists, plus a `<ReactFlowProvider>` wrapper.

**Design system**
- New paleta inspired by Linear/Vercel: deeper background with subtle violet
  glow, `surface` layered on a vertical gradient, indigo accent (`#6366f1`).
- Typography hierarchy with Geist Sans / Geist Mono and tabular-nums on stats.
- shadcn-style primitives: `Button` (5 variants), `Input`/`Textarea`/`Select`,
  `Card`/`PageHeader`/`Stat`, `Badge` with running pulse, `Dialog`, `Tabs`,
  `Toaster` (zustand-driven).
- Sidebar redesigned with logo, accent gradient, active-route indicator.
- Custom scrollbars and ReactFlow theme overrides.

**Real product features**
- `/agents/new` and `/agents/[id]/edit`: full UI to define an agent (name,
  model, description, body) — Rogologo writes the markdown to your AGENTS_DIR
  and the watcher picks it up. Validates name format and model whitelist.
- "Scaffold with Moragent" dialog inside the agent form, documenting the
  Moragent → Rogologo handoff.
- `/settings`: real form for Telegram + Slack tokens, allowed user IDs, and
  the agents/skills folder paths. Saving **hot-restarts the affected adapter
  or watcher** with no backend bounce. Live status pills indicate whether
  each subsystem is connected, configured-but-not-running, or absent.
- Persistent activity feed (`<ActivityFeed />`) on the operations page, fed by
  SSE, with pause/resume and click-to-run-detail.
- Operations page rebuilt: header with core health pill, four primary stats,
  live runs panel, agents preview grid, and the activity feed in a sticky
  side column.

**Backend**
- `core/runtime_state.py`: new mutable settings layer. Persists to
  `data/settings.json`, exposes `agents_dir/skills_dir/default_model/tokens`
  with masked public DTO. Adapters and registry now read from here, falling
  back to `core.config` when unset.
- `core/api/settings.py`: `GET /api/settings`, `GET /api/settings/status`,
  `POST /api/settings`. The POST hot-restarts Telegram, Slack, or the watcher
  depending on which fields changed.
- `core/api/agents.py`: `POST /api/agents` (create from UI, writes the .md),
  `PUT /api/agents/{id}` (edit, rename guarded), `GET /api/agents/{id}/source`
  (returns editable spec).


### Added
- Project bootstrap: layout, license (MIT), gitignore, .env.example
- Architecture document with full system diagram and data model
- Roadmap to public beta (Sprints 0-5)
- ADRs 001-004: stack, LLM auth, ant-farm, ontology + self-improving
- 5 specialized agents (architect, backend, frontend, devops, docs) with rich prompts
- 4 reusable skills (deploy, add-agent, schedule, self-improve)
- Backend (FastAPI + APScheduler + claude-agent-sdk 0.1.x)
  - Filesystem registry with hot reload (debounced watchdog)
  - Bounded-concurrency runtime orchestrator with cancellation
  - SSE event bus with glob topic patterns
  - SQLite + SQLAlchemy 2.0 async data layer
  - Telegram and Slack adapters (Slack via socket mode)
  - Ontology triple store with REST API
  - Self-improving reflection loop with diff queue (proposal-only, human-approved)
- Frontend (Next.js 15 + Tailwind v4 + react-pixi)
  - Pages: operations, agents, schedules, ant-farm, ontology, improvements, settings
  - Live SSE feed via `useStream` hook
  - 2D ant-farm with status-driven sprites (Pixi.js)
- Docker Compose default + prod profiles
- Windows installer (`install.bat` + `wizard.ps1`)
- GitHub Actions CI + Release workflows
- Bundled agent templates (brand-architect, daily-digest, inbox-watcher, maintenance)
- Bundled skill templates (rogologo-deploy, -add-agent, -schedule)

### Fixed (Sprint 1 verification — 2026-05-02)
- `core/runner/orchestrator.py`: `run:completed` and terminal events now carry the
  real agent name instead of a placeholder string.
- `core/config.py`: default `AGENTS_DIR`/`SKILLS_DIR` now point to the bundled
  `agents-templates/` and `skills-templates/`, so a fresh checkout discovers
  agents on first start.
- `core/requirements.txt`: pinned `claude-agent-sdk` to the 0.1.x line and
  relaxed transitive bounds (notably `pydantic>=2.11`) so MCP-driven dependencies
  resolve.

### Verified (Sprint 1)
- `python -m uvicorn core.main:app` boots cleanly with the four bundled
  templates auto-registered.
- `POST /api/agents/{id}/run` invokes the bundled `claude` CLI via
  `claude-agent-sdk` and persists tokens, cost, and session id.
- `pnpm dev` serves the dashboard at `:3000`; `/api/*` is proxied to the core
  on `:8000`. All seven UI routes return 200, SSE hook reconnects on error.

### Sprint 2 — Dashboard MVP (DONE, 2026-05-02)
- `core/db/models.py`: persist run `final_text` (Text, nullable) so the run
  detail panel can replay completed runs without re-streaming.
- `core/db/base.py`: lightweight column-add migrator runs on every `init_db`,
  so existing SQLite files pick up nullable schema additions without a wipe.
- `core/api/runs.py`: `/api/runs/{id}` now returns `final_text`.
- `core/api/stream.py`: optional `run_id` query param filters server-side so
  a run-detail subscription doesn't receive other agents' chatter.
- `core/runner/orchestrator.py`: writes `final_text` to the row on completion.
- Dashboard:
  - `/runs/[id]` — new page with prompt, live streaming output, tool-call
    timeline, token/cost stats, cancel button, error block, polling fallback.
  - `/agents/[id]` — real Run-now form with prompt textarea; submission
    redirects to the live `/runs/[id]` view.
  - `/agents` — search by name/description/model + status filter.
  - `/schedules` — full create form with cron presets, agent picker, prompt,
    enabled toggle; delete with confirm; agent name resolved from id.
  - `/improvements` — pending/approved/rejected tabs, syntax-coloured diff
    viewer (additions, deletions, hunks, headers), agent name resolution.
  - `/ontology` — interactive `react-flow` graph (typed colour-coded nodes,
    predicate edge labels, minimap, controls, circular layout) plus a
    type-summary header.
  - `useStream` accepts `runId` to wire the server-side filter.
- Verified end-to-end with a fresh run #2 returning persisted `final_text`.

## [0.1.0] - TBD

First public alpha.
