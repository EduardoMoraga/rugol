# Changelog

All notable changes to Rogologo are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
