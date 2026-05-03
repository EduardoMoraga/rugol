# Rogologo — Developer notes

Working notes for anyone touching the Rogologo codebase. The README is for
users; this file is for the people building the thing.

## Stack snapshot

| Layer | Choice | Notes |
|------|--------|-------|
| Backend | Python 3.12 + FastAPI + Uvicorn | async throughout |
| ORM | SQLAlchemy 2.x (async) + aiosqlite | also supports Postgres via `DATABASE_URL` |
| Schema migrations | hand-rolled column-add migrator in `core/db/base.py` | switch to Alembic when the list grows past ~10 |
| LLM bridge | `claude-agent-sdk` (subprocess to bundled `claude.exe`) | uses `setting_sources=["user","project","local"]` so subscription auth works |
| Scheduler | APScheduler (cron + interval) | persisted to SQLite |
| Bus | in-process pub/sub (`core/bus.py`) | exposed as SSE on `/api/stream` |
| Frontend | Next.js 15.1.4 App Router + Tailwind v4 + shadcn primitives | React 19 |
| Frontend data | `@tanstack/react-query` + custom `useStream` SSE hook | |
| Markdown | `react-markdown` + `remark-gfm` + `rehype-highlight` | dark theme CSS in `globals.css` |
| Canvas | Plain HTML5 Canvas (no react-pixi anymore) | clusters by project (Capa 9) |

## Local dev

```bash
# Backend (Python 3.12 venv)
cd C:\Moragent\04-LAB\rogologo
.\.venv\Scripts\Activate.ps1
pip install -r core/requirements.txt
uvicorn core.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (separate terminal)
cd dashboard
pnpm install
pnpm dev   # serves on http://127.0.0.1:3000 (proxies /api → :8000)
```

Auth: have `claude /login` already done on the machine. Set
`USE_SUBSCRIPTION=true` in `.env` to use Pro/Max, or unset and provide
`ANTHROPIC_API_KEY` to bill against the API.

## Migrations

Hand-rolled in `core/db/base.py::init_db`. The pattern:

```python
nullable_additions: list[tuple[str, str, str]] = [
    ("agents", "project_id", "INTEGER REFERENCES projects(id) ON DELETE SET NULL"),
    ("agents", "tools_json", "TEXT"),
    ("projects", "lessons_json", "TEXT"),
    # ...
]
```

Every entry is run idempotently on boot: if the column already exists, skip.
This means returning users (with an existing SQLite file from before a
schema change) get auto-upgraded with no manual step.

**Rules of the road**:
- Only use this for nullable columns. New tables are handled by
  `Base.metadata.create_all`.
- Never drop or rename columns this way. If you need that, switch to Alembic.
- Backfills (like the Workspace project adoption in
  `_ensure_workspace_project`) go in their own dedicated function, not here.

## Known issues & workarounds

### Next.js 15.1.4 + Turbopack + Windows + pnpm

**Symptom**: `pnpm build` fails with:
```
Error: Cannot find module 'C:\...\node_modules\.pnpm\next@15.1.4_.../node_modules/next/dist/compiled/jest-worker/processChild.js'
```

**Why**: Turbopack workers spawn child processes that resolve module paths
through pnpm's content-addressable store. After running `pnpm dev` (which
hot-reloads on file edits) and then immediately running `pnpm build`, the
.pnpm symlinks for `next` get corrupted in a way that pnpm itself doesn't
detect — `pnpm install` reports "Done" without fixing anything.

**Workaround** (run from `dashboard/`):
```powershell
Remove-Item -Recurse -Force node_modules, .next -ErrorAction SilentlyContinue
pnpm install
pnpm build
```

This burns ~15 seconds but succeeds reliably. Need to run once after every
significant frontend dependency change.

**Plan**: upgrade to Next 15.4+ (the bug is reportedly fixed there) and
re-evaluate. We've held off because the Tailwind v4 + Geist + Turbopack
combo on 15.1.4 is otherwise stable for us.

### PowerShell encoding for non-ASCII test bodies

When testing endpoints from PowerShell:
```powershell
# Wrong — PowerShell mangles "ó" before sending
$body = @{ name = "Marca Personal"; mission = "Construir credibilidad…" } | ConvertTo-Json
Invoke-RestMethod -Body $body  # FastAPI rejects with "error parsing the body"

# Right — explicit UTF-8 charset
[System.IO.File]::WriteAllText("$env:TEMP\body.json", $body, [System.Text.UTF8Encoding]::new($false))
Invoke-RestMethod -InFile "$env:TEMP\body.json" -ContentType "application/json; charset=utf-8"
```

This is a PowerShell quirk, not a backend bug. Bash + curl works fine.

## Architecture cheatsheet

The user-facing flow:

```
User idea
   │
   ▼
[Architect] → Proposal {project, agents, skills, schedules, ontology}
   │                          OR
   │                  [Templates] → curated Proposal
   ▼
[Deployer] → writes .md files + DB rows + schedules
   │
   ▼
Agents live under a Project (slug, mission, color, icon, lessons)
   │
   ▼
[Run-now / Chat] → enqueues a Run (carries session_id, task_type, advocate flag)
   │
   ▼
[Orchestrator] → loads agent + project, builds project_context (mission + lessons),
                  picks model (override > agent's default), spawns claude_agent_sdk
   │
   ▼
[Runner] → streams text deltas to bus, persists tokens/cost/session/final_text
   │
   ▼
[Bus → SSE → /api/stream] → dashboard receives live deltas
   │
   ▼
[After completion] → if advocate requested, spawn opus critique run
                   → if reflection due, spawn improvement proposal
```

## Capas (delivered features)

| Capa | What it added | Key files |
|------|---------------|-----------|
| 1 | Project-first model + migration + UI | `core/db/models.py::Project`, `core/api/projects.py`, `dashboard/src/app/projects/` |
| 2 | Multi-turn chat + markdown rendering | `dashboard/src/components/agents/agent-chat.tsx`, `dashboard/src/components/ui/markdown.tsx` |
| 3 | Per-project lessons + auto self-improve trigger | `core/runner/orchestrator.py::_build_project_context`, `core/api/projects.py` lessons endpoints |
| 4 | System 1/2 task type + devil's advocate | `RunNowBody.task_type` + `seek_devils_advocate`, `_spawn_devils_advocate` |
| 5 | Per-agent tool whitelist + Architect dir picker | `Agent.tools` JSON column, `tools` field in claude-agent-sdk options, `target_agents_dir` deploy override |
| 6 | Curated project templates | `core/templates/catalog.py`, `core/api/templates.py`, `TemplateCatalog` component |
| 7 | Promote-to-lesson everywhere | `PromoteToLessonButton` in chat + `PromoteRationaleButton` in /improvements |
| 9 | Ant farm clusters by project | `dashboard/src/components/ant-farm/ant-farm-canvas.tsx` |
| 10 | Onboarding emotional hero | `dashboard/src/components/projects/onboarding-hero.tsx` |

(Capa 8 — per-agent MCP servers — is the next planned addition.)

## Testing approach

There's no automated test suite yet. The verification pattern used during
development is:

1. **Schema change** → reset DB or rely on idempotent migrator + `_ensure_*`
   backfill. Verify with a quick `Invoke-RestMethod` listing.
2. **API change** → `Invoke-RestMethod` POST/GET dance. PowerShell scripts
   live in commit messages and chat history; consider promoting them to
   `tests/manual/*.ps1` if they're worth replaying.
3. **UI change** → `pnpm type-check && pnpm build && pnpm dev`, then hit
   the page with `Invoke-WebRequest -UseBasicParsing` to confirm 200 + a
   sane content length. Real browser verification still required for
   anything dynamic.
4. **End-to-end LLM behavior** → fire a real run with a prompt that would
   tempt the model into the failure mode you're trying to prevent (e.g.
   "use punchy verbs about AI" if testing a "no hype words" lesson) and
   read the output. The model self-reports tool restrictions when asked,
   which makes it a good oracle.

`pytest` + `playwright` are listed in `tests/` as the planned framework
but not in active use yet.

## File layout reminders

- `core/templates/catalog.py` is hand-curated. Adding a template = edit
  this file, restart the backend, the new template appears.
- `agents-templates/` is the **default** AGENTS_DIR for a fresh install.
  Real users typically point this elsewhere via Settings → Agents folder.
- `.env.example` is what the installer wizard copies to `.env` and fills.
- `dashboard/src/lib/api.ts` is the single source of TS types for the
  whole frontend. Keep it in sync with backend Pydantic models.
