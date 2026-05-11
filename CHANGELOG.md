# Changelog

All notable changes to Rogologo are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0-alpha] — 2026-05-10

**The Soul Layer release.** Every agent registered in Rogologo now inherits
identity, proactive memory, dual-track dispatch, and an evolutionary archive
of its own system prompt — without per-agent configuration. Inspired by the
Darwin Gödel Machine (Zhang/Hu/Lu/Lange/Clune, arXiv:2505.22954) and
Kahneman's dual-process theory.

### Soul-1 · Identity + proactive memory (ADR-006)
- `core/soul/identity.py` — identity block prepended to every system prompt:
  name, description, prior run count, persistent memory count. Built from
  immutable agent fields, so reflection writes to memory (not identity).
- `core/soul/auto_memory.py` — explicit policy block the agent reads on
  every run. Four memory kinds with examples: `user`, `feedback`,
  `project`, `reference`. Includes the "what NOT to save" rules and the
  `Why:`/`How to apply:` structure for feedback/project entries.
- `core/soul/tools.py` — in-process MCP server `rogologo-soul` exposing
  `save_memory`, `list_my_memories`, `forget_memory`. The `agent_name` is
  captured in closure for each run, so an agent can never write into
  another agent's memory.
- `core/soul/builder.py` — composes identity + rules into one block.

### Soul-2 · Dual-track dispatcher (ADR-007)
- `core/soul/dispatcher.py` — Haiku-based classifier labels each request
  S1 (fast/intuitive) or S2 (deliberate). Defaults to S2 on ambiguity.
  Bypasses cleanly when `SOUL_DUAL_TRACK_ENABLED=false` or the caller
  forced `model_override`.
- `core/soul/plan_then_execute.py` — opt-in wrapper that makes S2 runs
  emit "Plan → Critique → Answer" in a single round-trip. Toggle via
  `SOUL_PLAN_THEN_EXECUTE_ENABLED`. `extract_final_answer()` helper for
  adapters that want to send only the user-facing answer to Telegram/Slack.
- `runs.track`, `runs.classifier_confidence`, `runs.classifier_rationale`
  columns added. Dashboard shows an `S1 · fast` / `S2 · deliberate` badge
  on run detail and on the agent's recent-runs list, with the classifier
  rationale as tooltip.

### Soul-3 · Evolutionary archive (ADR-008)
- `core/soul/evolution/archive.py` — per-agent lineage on disk
  (`agent-soul/<agent>/lineage.json` + `versions/<id>.md`). Supports
  `propose / accept / reject / branch / rollback / record_metrics`.
- `core/soul/evolution/proposer.py` — generates 1-3 candidate mutations
  from recent run history. Opus-based, parses `===CANDIDATE n===` blocks.
- `core/soul/evolution/validator.py` — Opus self-critique scoring with
  an optional `golden_set.jsonl` per-agent. Score is informational, not
  a gate; humans always decide. Designed so adding a golden set later
  upgrades the validator without API changes.
- `core/soul/evolution/router.py` — deterministic A/B routing across
  active branches when `SOUL_EVOLUTION_AB_ENABLED=true`.
- REST API under `/api/agents/{id}/evolution/{...}`: list lineage,
  propose, validate, accept, reject, branch, rollback, get version body.
- `runs.agent_version_id` column added — every run is now attributable
  to a specific lineage version, so per-version metrics are honest.
- Dashboard: new `/agents/[id]/evolution` page with a list of versions
  ordered by recency, status badges, metrics per version, validation
  scores, and all lifecycle actions inline. "Evolution" button added to
  the agent detail header.

### Cross-cutting fixes
- `agent_body` (the `.md` body that defines the agent's persona) is now
  actually injected into the system prompt. Until v0.6 it was persisted
  in the DB but never reached the model — the agent ran with the
  Claude Code preset only. This was masked because Rogologo's bundled
  templates happen to be short. Soul-3 needed this fixed to be coherent
  (the body is the unit of evolution).
- `core/runner/claude_runner.py` system-prompt composition now layers:
  agent persona → platform rules → soul context → project context.
- `core/runner/orchestrator.py` calls the dispatcher before model
  selection, resolves the body via the evolutionary router, and folds
  run metrics back into the version's averages.

### Settings (`.env`)
- `SOUL_DUAL_TRACK_ENABLED` (default `true`) — toggle the classifier.
- `SOUL_CLASSIFIER_MODEL` (default `claude-haiku-4-5-20251001`).
- `SOUL_PLAN_THEN_EXECUTE_ENABLED` (default `false`).
- `SOUL_EVOLUTION_AB_ENABLED` (default `false`).
- `SOUL_PROPOSER_MULTIPLIER` (default `1.0`).

### Testing
- 43 pytest cases green: Soul-1 (10), Soul-2 dispatcher (16), Soul-3
  evolution (14), legacy smoke (3). Proposer + validator + REST endpoints
  are integration-tested with the live SDK; unit tests cover all pure logic
  (parsing, file ops, routing, metric folding).

### Migration
SQLite migrator is idempotent and runs on boot. Adds nullable columns:
`runs.track`, `runs.classifier_confidence`, `runs.classifier_rationale`,
`runs.agent_version_id`. No data loss. The new `agent-soul/` directory is
created on demand the first time the evolution UI is opened or the
proposer fires.

### Known limitations
- The validator without a curated `golden_set.jsonl` operates on Opus
  self-critique only. Scores are a second opinion, not a gate. Curate a
  golden set per agent once you have enough runs with thumbs-up signal.
- Cross-agent evolution (one agent's discovery flowing to another) is
  not implemented. ADR-008 sketches the design.

## [0.5.0-alpha] — 2026-05-04

**Primer release coherente, instalable y demostrable en una PC limpia.** Pasamos de "scaffold con dashboard" a "sistema operativo de agentes" con paradigma project-first, lecciones vivas, sistema 1/2 explícito, devil's advocate, y templates listos para clonar en un click.

### 15 capas entregadas en este ciclo

| Capa | Aporte |
|---|---|
| 1 | **Project-first model**. La unidad de cuenta es el proyecto, no el agente. Migración no destructiva, `/projects` como home, Architect siempre produce un proyecto con misión. ADR-005. |
| 2 | **Chat multi-turn + markdown clickeable**. `session_id` encadena turnos (verificado: el agente recuerda "mauve" entre mensajes). Output con react-markdown + syntax highlight + links clickeables. |
| 3 | **Lecciones vivas + auto self-improve**. Cada proyecto tiene un banco de `{kind, text}` que se inyecta al system prompt en cada run. Auto-trigger del reflector cuando un agente acumula fallos o hits N runs. |
| 4 | **Sistema 1/2 + devil's advocate**. Selector heurística/pensar/deliberar rutea al modelo apropiado (haiku/agente/opus). Checkbox dispara crítica con opus en run secundario, anidada en la misma conversación. |
| 5 | **Tools editables por agente + dir picker en Architect**. Whitelist de herramientas built-in vía frontmatter. Override de install dir por deploy. Verificado: el modelo reporta solo las tools whitelisteadas en runtime. |
| 6 | **5 templates curados**. Asistente personal, Mi hija aprende jugando, Marca personal, Pipeline comercial, Investigador. Clone en un click con auto-rename para duplicados (agentes y schedules). |
| 7 | **Promote-to-lesson**. Cierre del loop pedagógico: cualquier respuesta del agente o crítica del advocate se promueve a lección del proyecto con un click. |
| 8 | **MCP servers por agente**. Configuración stdio/sse/http per-agent. UI para agregar/quitar. Conectar Asana, Notion, Slack al agente sin tocar el `.env` global. |
| 9 | **Ant farm con clusters**. Visualización HTML5 Canvas que agrupa agentes por proyecto. Halo del color del proyecto, dot del color del status. |
| 10 | **Onboarding emocional**. Hero de primer-uso con la cita "La vida es la sumatoria de proyectos. Tú eres el CEO; ellos ejecutan." Desaparece al primer proyecto real. |
| 11 | **Health check extendido + DEVELOPMENT.md**. `/api/health/full` reporta schema y actividad 24h. Documentación interna para devs + workaround del bug Next 15+pnpm en Windows. |
| 12 | **READMEs reescritos**. EN+ES desde cero, paradigma project-first como entrada, casos reales (incluyendo el de la hija), 5 templates listados con descripción concreta. |
| 13 | **Channel bindings (Telegram/Slack)**. Tabla `channel_bindings`, comandos `/bind`, `/whoami`, `/agents` en bot. Reply-on-completion vía bus subscriber. Sin binding → mensaje de ayuda, nunca dispatch a agente equivocado. |
| 14 | **Reset a estado limpio**. `scripts/reset.py` + `POST /api/admin/reset` + botón en Settings → Zona peligrosa. `docs/install-on-new-pc.md`. Backend ya no muere si Telegram timeout en arranque. |
| 15 | **Toggle EN/ES**. Provider i18n minimalista (no next-intl) con localStorage. Toggle en nav rail. Pantallas core traducidas: nav, /projects, OnboardingHero, TemplateCatalog, NewProjectDialog, AgentCard, AgentChat. |

### Fixes notables

- **`setting_sources=["user"]`** en el SDK: los agentes ya no leen el `CLAUDE.md` del repo. Antes respondían "te ayudo con Rogologo Sprint 2" — ahora cada agente responde según su template y el proyecto en el que vive.
- **Mojibake fix**: `scripts/fix_mojibake.py` repara doble-encoding UTF-8→Latin-1 en `.md` corruptos por tests con PowerShell.
- **Polling fallback** en agent-chat: si la SSE se desconecta (ej. backend restart), un poll cada 4s al `/api/runs/{id}` hidrata el turno desde el `final_text` persistido.
- **Backend resiliente al startup**: si Telegram/Slack falla, se loguea y el resto de la app sigue.
- **Audit fixes**: cron validado con `CronTrigger.from_crontab` antes del DB insert; orden inverso en delete schedule; React keys compuestas en lists con SSE.
- **React hooks order** en RunDetail (useMemo después de early returns), `<a>` dentro de `<a>` por ProjectBadge en AgentCard, `<option>` blanco-sobre-blanco en Chromium light theme.

### Verificación end-to-end

- 23/23 endpoints API → 200 con shapes correctas
- 16/16 rutas UI → renderizan
- Channel binding cycle (create/lookup/replace/delete) → limpio
- Cron validation → bad cron 400, good cron 201
- Run con `task_type=fast` sobre opus agent → ruteado a haiku ($0.13 vs $0.60)
- Run con `seek_devils_advocate=true` → primary aplica lecciones del proyecto, advocate cuestiona específicamente

### Stack final

- **Backend**: Python 3.12, FastAPI, async SQLAlchemy, SQLite (Postgres opcional), APScheduler, claude-agent-sdk, python-telegram-bot, slack-bolt
- **Frontend**: Next.js 15 + React 19 + Tailwind v4, react-query, react-markdown + remark-gfm + rehype-highlight, HTML5 Canvas
- **i18n**: provider casero ES/EN con localStorage
- **DB**: 5 tablas core (`projects`, `agents`, `runs`, `messages`, `schedules`) + 4 secundarias, todas con migración no destructiva idempotente

---

## [Unreleased]

### Sprint 4 — Architect (the OpenClaw gap closer, 2026-05-02)

This is the answer to the question "why would I pick this over OpenClaw". The
Architect turns a one-line idea into a complete, editable proposal — agents,
skills, schedules, ontology seeds — and ships it to disk on approval. End to
end inside the dashboard.

**New: the Architect flow**
- `/architect` — three-stage page (idea → review → done) where you describe
  the outcome you want. A meta-prompt asks Claude Sonnet 4.6 to design the
  smallest coherent stack that delivers it. The proposal returns as a JSON
  payload that you review and edit *card by card* before deploying.
- Every proposed agent, skill, schedule, and ontology triple is editable
  inline. Add/remove agents, retitle skills, adjust cron expressions, drop
  triples you do not want.
- "Deploy" writes the markdown files into `AGENTS_DIR`/`SKILLS_DIR`, creates
  the schedules in APScheduler, seeds the ontology — and shows a result card
  with what was created / skipped (existing files are never overwritten).
- Backend: `core/architect/proposer.py` (META_PROMPT + JSON parsing),
  `core/architect/deployer.py` (file writes + scheduler/ontology integration),
  `core/api/architect.py` (`POST /api/architect/propose` + `/deploy`).
- Tested end-to-end with the LinkedIn idea — Architect returned a
  honestly-scoped two-agent design (a haiku-based week-harvester and a
  sonnet-based linkedin-drafter) with a candid rationale section and called
  out what wouldn't work yet (no LinkedIn API).

**Agent detail with real tabs**
- `/agents/[id]` rebuilt with tabs: **Overview** (run-now + recent runs),
  **Spec** (full prompt body, syntax-friendly read-only view),
  **Memory** (shared ontology with provenance roadmap noted),
  **Tools** (the inherited Claude Code toolkit, with whitelisting roadmap).

**Skills as first-class**
- `/skills` lists every registered skill with description and an "open spec"
  dialog showing the full markdown.
- Backend: `GET /api/skills`, `GET /api/skills/{id}`, `POST /api/skills`,
  `PUT /api/skills/{id}`. The Architect already creates skills as part of a
  deploy.

**Bugs fixed**
- Operations stat showed *Received NaN for the children attribute* because
  `/api/runs` did not return `input_tokens`/`output_tokens`. Backend now
  returns them; frontend has defensive `Number(x) || 0` coalescing.

**Plumbing**
- `next.config.ts` — `experimental.proxyTimeout = 240_000` so the dashboard
  proxy survives the Architect's 15-40s LLM call.
- Nav rail: Architect added as the primary CTA (accent-tinted), Skills slot
  added.
- Operations / agents pages: empty states and primary CTAs now point to the
  Architect first, manual creation second.


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
