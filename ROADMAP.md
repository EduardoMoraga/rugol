# Rugol — Roadmap

> Each sprint is two weeks. Goal: ship a public beta in 8 weeks.
> Track issues with the matching label on GitHub.

> **Nota de estado (2026-08-28).** Este documento se escribió al principio y la
> numeración de sprints se desacopló de la de releases: el producto va en
> 0.9.0-alpha y los sprints 1, 2, 8 y 9 están hechos, mientras el 3 sigue
> abierto por una sola cosa —el instalador nunca se probó en una PC Windows
> **limpia**; en el NUC fue una reparación sobre una instalación existente—.
> Para el estado real, la fuente es `CHANGELOG.md` y la sección Status de
> `CLAUDE.md`; esto de acá abajo es el plan original y se conserva como tal.

## Sprint 0 — Bootstrap (DONE)

- [x] Project scaffold, agents created, docs written, decisions captured
- [x] Repo layout, license, gitignore
- [x] Architecture and ADRs published
- [x] CLAUDE.md guides every future agent invocation

## Sprint 1 — Backend MVP (week 1-2)

**Goal:** A user can run `python -m core.main`, hit `/api/agents`, and see a
list of `.md` files registered. They can `POST /api/runs` to fire an agent and
stream its output via SSE.

**Tickets:**
- `feat(core): FastAPI app skeleton with health, agents, runs, schedules, sse`
- `feat(core): SQLite + SQLAlchemy async + alembic migrations`
- `feat(core): filesystem registry that auto-loads agents/*.md and skills/*.md`
- `feat(core): RuntimeOrchestrator with semaphore + bus + claude-agent-sdk runner`
- `feat(core): APScheduler integration with cron + one-shot triggers`
- `feat(core): Telegram adapter ported from eduagent-gateway`
- `feat(core): Slack adapter (Bolt for Python, socket mode)`
- `test(core): pytest fixtures for an in-process FastAPI client`

**Definition of done:** running `pytest` passes; running `uvicorn core.main:app`
shows a healthy app with a sample agent loaded; sending a Telegram message
triggers a real Claude run and replies.

## Sprint 2 — Dashboard MVP (week 3-4)

**Goal:** A user opens `http://localhost:3000` and sees their agents as cards
with live status. Clicking one opens a detail panel with run history, schedules,
and a "Run now" button. The ant-farm renders all agents as sprites.

**Tickets:**
- `feat(dashboard): Next.js 15 App Router + Tailwind v4 + shadcn baseline`
- `feat(dashboard): /api proxy + SSE hook (useStream)`
- `feat(dashboard): Agents list page with cards, status badges, search`
- `feat(dashboard): Agent detail panel with tabs (overview, runs, schedules, memory)`
- `feat(dashboard): Schedules CRUD UI with cron picker`
- `feat(dashboard): Run history timeline with cost/tokens columns`
- `feat(dashboard): Ant-farm canvas with react-pixi (hex grid + sprites)`
- `feat(dashboard): EN/ES i18n with next-intl`
- `feat(dashboard): Empty states for every list (zero agents, zero runs, etc.)`

**Definition of done:** Lighthouse mobile > 90; ant-farm runs at 60 fps with
30 agents; all strings translated.

## Sprint 3 — Distribution (week 5-6)

**Goal:** A non-developer on a clean Windows 11 box can install Rugol and
have a working dashboard in under 10 minutes.

**Tickets:**
- `feat(installer): Windows .bat that calls a PowerShell wizard`
- `feat(installer): preflight (Docker Desktop, Node 20, Claude Code CLI)`
- `feat(installer): interactive token capture with masked input`
- `feat(installer): claude /login passthrough`
- `feat(installer): docker compose up + open browser`
- `feat(devops): docker-compose.yml with profiles (default + prod)`
- `feat(devops): GitHub Actions release workflow (build images, attach assets)`
- `feat(devops): docker-compose health checks for every service`
- `docs: quickstart with screenshots`

**Definition of done:** ships v0.1.0 to GitHub Releases; the install video
is < 90 seconds end-to-end.

## Sprint 4 — Differentiators (week 7-8)

**Goal:** The features no other open project has — ant-farm polish, ontology,
self-improving, teams in Slack — are demoable and stable.

**Tickets:**
- `feat(core): ontology triple store + MemoryWrite tool exposed to agents`
- `feat(dashboard): ontology graph viewer (react-flow)`
- `feat(core): self-improving loop with reflection prompt + diff queue`
- `feat(dashboard): improvement review UI (approve/reject diff)`
- `feat(core): teams — multiple agents bound to one Slack channel`
- `feat(core): @mention routing + agent-to-agent handoff`
- `feat(dashboard): chat replay viewer (rerun a session)`
- `polish: ant-farm sprites, sound effects toggle, dark/light theme`

**Definition of done:** demo video shows a Slack channel where three agents
collaborate, ontology graph grows during the demo, and one agent's diff is
approved live.

## Sprint 5 — Public Beta (week 9-10)

**Goal:** Make it real-world ready and invite the world.

- `chore: hardening (rate limits, error budgets, log redaction)`
- `chore: typed Python (mypy strict on core/)`
- `feat: import wizard for existing .claude/agents/ folders elsewhere on disk`
- `feat: telemetry (opt-in) for usage stats`
- `docs: contribution guide, code of conduct, security policy`
- `marketing: launch on Show HN, r/LocalLLaMA, X, LinkedIn`
- `marketing: 60-second product video`
- `marketing: write to Anthropic devrel`

## Sprint 6 — Ambient Layer / Atalaya (ADR-010)

**Goal:** Rugol stops being unidirectional. The watchtower observes the user's
world and, by its own judgment, surfaces only what matters — proactively. This
is the "soul made outward-facing": the defensible, hard-to-commoditize core.

Phasing is a *precision-discovery ladder*, validated on the author's real inbox,
not a feature checklist (see ADR-010):

- `feat(ambient): Sensor protocol + Observation/Signal/RelevanceWeight schema`
- `feat(ambient): salience scorer (Haiku, clone of soul/dispatcher shape)`
- `feat(ambient): fail-closed two-tier gate (interrupt budget + quiet hours)`
- `feat(ambient): gmail sensor → daily digest to Telegram (Phase 0, no interrupts)`
- `feat(ambient): feedback buttons + EWMA per-scope weight learning (Phase 1)`
- `feat(ambient): interrupt tier + calendar/asana/pipeline/youtube/files sensors`
- `feat(ambient): suggested-action one-tap (draft reply / propose task) + WhatsApp`
- `feat(dashboard): Atalaya page — observation stream, sensor toggles, budget gauge`

**Definition of done:** with `AMBIENT_ENABLED=true`, a single real sensor runs a
full week on the author's inbox, the digest precision is measured, the noise rate
falls measurably after feedback, and **not one** false interrupt fires before the
scorer is tuned. The gate's asymmetry invariants are unit-tested.

## Beyond v1 (backlog)

- Linux & macOS installers
- Mobile PWA wrapper
- Multi-LLM (OpenAI / local Ollama) via pluggable runners
- RBAC and multi-user
- Hosted Cloud SaaS edition
- Marketplace for community-published agents

## Success metrics

| Metric | Target |
|--------|--------|
| GitHub stars at launch + 30 days | ≥ 500 |
| Install-to-first-run time | ≤ 10 min |
| Crash-free sessions | ≥ 99% |
| Active installs reporting telemetry | ≥ 100 in 60 days |
| Anthropic devrel response | "Let's chat" 🤝 |
