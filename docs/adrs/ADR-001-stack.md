# ADR-001 — Choice of stack

**Status:** Accepted · 2026-05-02 · Author: rogologo-architect

## Context

Rogologo needs a stack that is:

1. **Familiar to the maintainer** (Eduardo Moraga) — Python and TypeScript
   are his daily drivers. Forcing Go or Rust would slow iteration.
2. **Friendly to non-developers installing it** — the installer must work
   on a vanilla Windows PC. That points to Docker Compose.
3. **Capable of real-time fan-out** — the dashboard must show agents working
   live. Polling is unacceptable; SSE/WebSockets are.
4. **Boring on the hard parts** — we are building agentic infra, not a
   distributed database. Pick the most boring options for storage and
   transport so the interesting code lives in the agent layer.

## Decision

| Layer | Choice | Why this, not the alternative |
|-------|--------|-------------------------------|
| Backend lang | **Python 3.12** | `claude-agent-sdk` is Python; we already have a working Python adapter (`eduagent-gateway`); the maintainer ships Python daily. |
| Web framework | **FastAPI + Uvicorn** | First-class async, auto-docs at `/docs`, SSE support via Starlette. Alternative Flask is sync-first; alternative Litestar is less known. |
| Scheduler | **APScheduler 3** | Battle-tested, persistent jobstore on SQLite, supports cron and interval. Alternative Celery is overkill for one host; alternative Temporal needs a dedicated server. |
| DB | **SQLite (default)** + **Postgres (opt-in)** | SQLite zero-install for personal PC; Postgres swap is one env var. SQLAlchemy Async hides the difference. Alternative: Postgres-only would make the installer drag in a 200 MB image needlessly. |
| Migrations | **Alembic** | Standard with SQLAlchemy. |
| Frontend | **Next.js 15 App Router** | The maintainer has shipped Next.js apps; SSR + RSC fit the dashboard's mix of static and live data; great DX. Alternative Vite + React-Router would force us to build SSR ourselves. |
| Styling | **Tailwind v4** | Maintainer uses Tailwind in `mission-control` and `Albert/portal-bi-increxa`. Alternative CSS-in-JS adds runtime cost. |
| Components | **shadcn/ui** | Owned source, no npm coupling, accessible by default. Alternative Material UI is heavy and opinionated. |
| Real-time | **Server-Sent Events** | One-way fan-out is exactly what we need; trivial to proxy through Next.js; no WebSocket session management. WebSocket is reserved for v2 if we add bi-directional collab. |
| Distribution | **Docker Compose** | Encapsulates Python + Node + DB into a single `docker compose up`; works identically on Windows/macOS/Linux. Alternative native bundles per-OS triple the maintenance. |
| Container OS | **`python:3.12-slim` + `node:20-alpine`** | Smallest viable bases. |

## Consequences

- **Positive:** Boring pieces stay boring; the interesting code is in the
  orchestrator + ontology + self-improver, exactly where we want our
  attention.
- **Positive:** New contributors with Python/TS background can be productive
  in hours.
- **Positive:** Migration to Postgres later is one env var; migration to
  another web framework later is a rewrite — but unlikely needed.
- **Negative:** Docker Desktop is a heavy dependency on Windows. We mitigate
  by checking for it in the installer and pointing the user to download.
- **Negative:** Two languages mean two build pipelines. We accept this; the
  alternative (rewriting in TS or Python only) would harm one of frontend
  DX or backend maturity.

## Alternatives rejected

- **All-Python with HTMX**: nice for a hackathon, but the ant-farm needs WebGL
  and the dashboard needs RSC patterns. HTMX would slow us down.
- **All-TypeScript with `@anthropic-ai/sdk`**: would force us to drop the
  battle-tested `eduagent-gateway` Python adapter and re-implement the
  Telegram + audio + file-handling pipeline. Not worth it.
- **Tauri desktop app**: tempting for a "one .exe install", but it forces us
  to bundle Python *and* Node runtimes into the app, doubling complexity for
  marginal UX. Docker Desktop wins on long-term maintenance.
