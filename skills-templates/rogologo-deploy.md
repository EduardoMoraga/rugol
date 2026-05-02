---
name: rogologo-deploy
description: End-to-end deploy / update of a Rogologo instance on a clean Windows PC.
---

# /rogologo-deploy

Use when starting fresh or upgrading an existing install.

## Steps

1. **Preflight** — verify Docker Desktop, Node.js 20+, Claude Code CLI present.
2. **Update repo** — `git pull` if existing, otherwise `git clone`.
3. **Wizard** — run `installer/wizard.ps1` to refresh `.env` if changed.
4. **Pull images** — `docker compose pull`.
5. **Migrate** — `docker compose run --rm core alembic upgrade head` (post-Sprint 1).
6. **Up** — `docker compose up -d`.
7. **Wait healthy** — poll `/api/health` until 200.
8. **Open** — open `http://localhost:3000` in default browser.

## Output

Confirmation message with the running version, number of registered agents,
and active schedules. Plus the URL to the dashboard.
