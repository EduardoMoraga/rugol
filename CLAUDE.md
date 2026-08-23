# Rugol — Open-Source Agentic Operations Platform

> **Vision:** Rugol is the control plane every Claude developer wishes existed.
> Drop it on a Windows PC, point it at your `.claude/agents/`, and watch your agents
> work — schedule them, chat with them from Telegram/Slack, and see them as living
> sprites in a 2D ant-farm. Open source, MIT, ready for a Show-HN moment.

## Identity

You are working on **Rugol**, an open-source orchestration & observability layer
for Claude Code agents. The product fuses two ideas Eduardo Moraga already
prototyped:

1. **Moragent** (`.claude/skills/moragent.md`) — a CLI plugin that scaffolds and
   enriches agentic infrastructure inside any Claude Code project.
2. **EduAgent Gateway** (`04-LAB/eduagent-gateway/`) — a Telegram-to-Claude-Agent-SDK
   bridge that lets you operate the workspace from a phone.

Rugol is the **next step**: a self-contained product (Docker Compose, Windows
installer, Next.js dashboard, FastAPI core) that turns a single PC into an
**agent operations center**. Multi-channel chat ops + recurring schedules +
visual fleet view + shared ontology + self-improving loop.

The end goal is a project worth showing publicly — and worth Anthropic noticing.

## Stack (locked unless ADR says otherwise)

| Layer | Choice | ADR |
|------|--------|-----|
| Backend runtime | Python 3.12 + FastAPI + Uvicorn | ADR-001 |
| Scheduler | APScheduler (cron + interval triggers) | ADR-001 |
| Database | SQLite (default) + Postgres (prod opt-in) | ADR-001 |
| LLM bridge | `claude-agent-sdk` (subprocess to `claude` CLI) | ADR-002 |
| LLM auth | Subscription Pro/Max **or** Anthropic API key | ADR-002 |
| Frontend | Next.js 15 App Router + Tailwind v4 + shadcn | ADR-001 |
| Real-time | Server-Sent Events (SSE) over `/api/stream` | ADR-001 |
| Visualization | `react-pixi` for the ant-farm 2D scene | ADR-003 |
| Memory graph | SQLite triple store (subject-predicate-object) | ADR-004 |
| Self-improving | Reflection loop with human-in-the-loop approval | ADR-004 |
| Containerization | Docker Compose (4 services) | ADR-001 |
| Distribution | GitHub Releases + Windows `.bat` installer | ADR-001 |

## Agents

| Agent | Model | Owns |
|-------|-------|------|
| `rugol-architect` | opus | Architecture decisions, ADRs, security, cross-stack coherence |
| `rugol-backend` | sonnet | FastAPI core, scheduler, adapters, ontology, self-improving |
| `rugol-frontend` | sonnet | Next.js dashboard, panels, ant-farm visualization |
| `rugol-devops` | sonnet | Docker, GitHub Actions, releases, Windows installer |
| `rugol-docs` | haiku | Bilingual docs (EN/ES), README, screenshots, promo material |

When the user asks for cross-cutting changes, **delegate to the right agent**.
When in doubt, ask `rugol-architect` first.

## Skills

- `/rugol-deploy` — End-to-end deploy on a clean Windows PC
- `/rugol-add-agent` — Register a new agent in DB + dashboard
- `/rugol-schedule` — Create a recurring schedule for an agent
- `/rugol-self-improve` — Run the reflection loop on an agent

## Layout

```
04-LAB/rugol/
├── CLAUDE.md                 (this file)
├── README.md                 (English)
├── README.es.md              (Spanish)
├── ARCHITECTURE.md           (deep-dive diagrams + data flow)
├── ROADMAP.md                (sprints 1–4 → public beta)
├── LICENSE                   (MIT)
├── .gitignore
├── docker-compose.yml
├── .env.example
├── core/                     (Python FastAPI backend)
│   ├── main.py               (app entrypoint)
│   ├── config.py             (settings)
│   ├── db/                   (SQLite models + migrations)
│   ├── registry/             (agents + skills loader)
│   ├── scheduler/            (APScheduler wrapper)
│   ├── adapters/             (telegram, slack, mcp)
│   ├── ontology/             (memory graph)
│   ├── improvements/         (self-improving loop)
│   ├── api/                  (REST + SSE endpoints)
│   ├── Dockerfile
│   └── requirements.txt
├── dashboard/                (Next.js 15 frontend)
│   ├── package.json
│   ├── Dockerfile
│   └── src/
│       ├── app/              (App Router pages)
│       ├── components/
│       │   ├── dashboard/    (cards, stats, run history)
│       │   ├── ant-farm/     (react-pixi scene)
│       │   └── ui/           (shadcn primitives)
│       └── lib/              (api client, sse hook)
├── cli/
│   ├── rugol                 (Mac/Linux launcher — setup, up, login, doctor…)
│   ├── rugol.ps1             (Windows launcher, mirrors the bash one)
│   ├── rugol.cmd             (cmd.exe shim → rugol.ps1)
│   └── rugol-auth.py         (login/logout/auth — shared by both launchers)
├── installer/
│   ├── install.ps1           (Windows one-liner: uv + Node + launcher + build)
│   └── install.sh            (Mac/Linux one-liner)
├── agents-templates/         (4 starter agents bundled with the install)
├── skills-templates/         (3 starter skills bundled)
├── docs/
│   ├── adrs/                 (architecture decision records)
│   ├── quickstart.md
│   ├── install-on-new-pc.md  (native install, auth, verification)
│   ├── remote-access.md      (Tailscale — never change the bind)
│   ├── troubleshooting.md
│   └── screenshots/
├── scripts/                  (dev helpers)
└── tests/                    (pytest + playwright)
```

## Working principles for Claude in this project

1. **Quality over speed.** This project is a public-facing showcase. No
   placeholder text, no broken features, no half-baked UI. If you can't ship
   it polished, document the gap and skip it.
2. **Bilingual first-class.** Every user-facing string in EN and ES. Code
   comments and ADRs in English. README.md (EN) is the canonical entry; the
   ES version mirrors it.
3. **Reuse `eduagent-gateway`.** Don't rewrite the Telegram adapter — port the
   battle-tested code from `04-LAB/eduagent-gateway/gateway.py`. Same for
   single-instance lock, attachment download, audio transcription.
4. **Treat the dashboard as a product**, not a debug tool. Every panel must
   have an empty state, a loading state, and a real value proposition.
5. **No secrets in code.** All tokens via `.env` and `.env.example`. The
   installer wizard writes the real `.env`.
6. **Default to Subscription auth.** Most demo users will have Claude Pro/Max,
   not API credits. API key is the fallback.
7. **Document decisions.** Every non-obvious choice gets an ADR in `docs/adrs/`.
8. **Honor Edu's preferences.** Spanish in conversation, no emoji unless
   asked, action-oriented, professional tone.

## Status

**Sprint 0 — Bootstrap (DONE)**
- [x] Project scaffolded
- [x] Architecture + ADRs documented
- [x] Backend skeleton runnable (`uvicorn core.main:app`)
- [x] Frontend skeleton runnable (`pnpm dev`)
- [x] Docker Compose definition + prod profile
- [x] Windows installer (`installer/install.ps1` + `cli/rugol.ps1`)

**Sprint 1 — Backend MVP (DONE, 2026-05-02)**
- [x] FastAPI app boots cleanly, bundled templates auto-register
- [x] `POST /api/agents/{id}/run` invokes `claude-agent-sdk` end-to-end
- [x] Tokens, cost, session id persist; status transitions emit bus events
- [x] Dashboard `pnpm dev` serves all 7 routes, proxies `/api/*` to core
- [x] All 4 bundled templates load on first scan
- [x] Local dev quickstart documented in `docs/quickstart.md`

**Sprint 2 — Dashboard MVP (DONE, 2026-05-02)**
- [x] Run detail page `/runs/[id]` with live SSE streaming + cancel
- [x] Agent detail Run-now form, redirects to live run view
- [x] Agents list search + status filter
- [x] Schedules CRUD UI with cron presets and delete
- [x] Improvements review with pending/approved/rejected tabs and coloured diff
- [x] Ontology graph with react-flow (typed nodes, predicate labels, minimap)
- [x] Backend: persisted `final_text`, run_id-filtered SSE, idempotent
      column-add migrator for SQLite

**Sprint 7 — Auth operable (DONE, 2026-08-22)**
- [x] `rugol login` / `logout` / `auth` in both launchers — surgical `.env`
      edits, never the full `rugol setup` rewrite
- [x] `core/runner/claude_cli.py` resolves the CLI the SDK actually runs (the
      one bundled in the wheel) and reports which credential won
- [x] Two-level check: `auth status` for config (cheap, polled) and a real
      minimal API call for validity — `auth status` reports a revoked token as
      connected, so `doctor` used to pass on credentials that never worked
- [x] `GET /api/health/auth[?verify=true]` + "Cuenta de Claude" card in
      `/settings`
- [x] Run failures surface their reason in the chat, with a `rugol login` hint
      when the error looks like auth
- [x] Mutable state moved out of the app dir (`RUGOL_DATA_DIR`), with one-time
      adoption of `settings.json` / `scheduler.db` from the old location
- [x] Model catalogue on the current generation, single source of truth, legacy
      IDs still accepted
- [x] Docs rewritten for the native install: `install-on-new-pc`,
      `troubleshooting`, new `remote-access` (Tailscale)

**Next: Sprint 3 — Windows installer verified on a clean PC, release v0.1.0
with screenshots and a < 90-second video. Sprint 4 — teams in Slack +
self-improving loop hardening. Sprint 5 — public launch.**

See `ROADMAP.md` for sprints 3–5 toward public beta.
