<div align="center">

# Rogologo

**The open-source operations center for Claude Code agents.**

Schedule them. Chat with them from Telegram & Slack. Watch them work in a 2D ant-farm.
One Windows PC. One Docker command. Zero lock-in.

[Quickstart](#quickstart) · [Why](#why-rogologo) · [Architecture](ARCHITECTURE.md) · [Roadmap](ROADMAP.md) · [Español](README.es.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Next.js%2015-blue)]()
[![Status](https://img.shields.io/badge/status-alpha-orange)]()

</div>

---

## Why Rogologo

If you build with Claude Code, you probably have a `.claude/agents/` folder full
of carefully tuned subagents — and a vague feeling they could be doing more.
You'd love to:

- Run them on a schedule (a "marketing" agent that posts every Monday).
- Chat with them from your phone instead of opening VS Code.
- See which one is busy, which one failed last night, which one is idle.
- Have a few agents talk to each other inside a Slack channel.
- Let them improve their own prompts based on past runs.

Rogologo is the missing control plane for that. It runs locally on a Windows PC
(no cloud, no SaaS), reads your existing `.claude/agents/`, and gives you:

- A **dashboard** with live status, run history, costs, logs.
- A **scheduler** with cron triggers and one-shot tasks.
- **Telegram and Slack adapters** that route messages to the right agent.
- An **ant-farm view** — a 2D scene where each agent is a sprite that wakes up
  and moves when working. Pure visual joy.
- A **shared ontology** — a graph of concepts, entities, and relationships
  every agent can read from and write to.
- A **self-improving loop** — after each run, the agent reflects, proposes
  edits to its own `.md`, and waits for your approval.

## Quickstart

### Requirements

- Windows 10/11 (Linux & macOS support tracked in [#3](https://github.com/eduardomoraga/rogologo/issues/3))
- An [Anthropic account](https://console.anthropic.com) — Pro/Max subscription **or** API key
- 8 GB RAM, 10 GB disk

### Install (one-line)

```powershell
git clone https://github.com/eduardomoraga/rogologo.git
cd rogologo
.\installer\install.bat
```

The wizard will:
1. Check & install **Docker Desktop**, **Node.js**, **Claude Code CLI** if missing
2. Walk you through `claude /login` (uses your subscription, no API charges)
3. Optionally collect a **Telegram bot token** and **Slack token**
4. Generate `.env` and run `docker compose up -d`
5. Open the dashboard at <http://localhost:3000>

### Add your first agent

Drop any `.md` file with frontmatter in `agents/`:

```markdown
---
name: brand-architect
model: opus
description: Posts to LinkedIn every Monday with curated takes.
---

You are a personal-brand strategist for Eduardo. Each Monday at 9 AM you...
```

It appears in the dashboard within 5 seconds. Click "Schedule", pick a cron, done.

## What's inside

```
core/        Python FastAPI backend (registry, scheduler, adapters, ontology)
dashboard/   Next.js 15 + Tailwind v4 frontend (with react-pixi ant-farm)
installer/   Windows wizard (.bat + .ps1)
docs/        Architecture, ADRs, screenshots
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the deep-dive.

## What works today (v0.1.0-alpha)

Verified end-to-end on Windows 11 + Python 3.12 + Node 20:

- ✓ Drop a `.md` into `agents-templates/`, it appears in the dashboard within
  5 seconds (debounced watchdog).
- ✓ Click **Run** on any agent, type a prompt, get redirected to a live
  `/runs/[id]` page that streams the assistant's output token-by-token,
  shows tool calls as they happen, and persists the final text + token cost
  + session id to SQLite.
- ✓ Create a recurring schedule with a cron expression and a prompt; the
  job survives restart (APScheduler SQLite jobstore).
- ✓ Browse the **ontology** as an interactive react-flow graph with typed
  nodes (concept / entity / event) and labelled predicate edges.
- ✓ Review **self-improvement** proposals on a tabbed page with a
  syntax-coloured diff viewer; every change requires explicit approval.
- ✓ Bundled `claude` CLI is invoked via `claude-agent-sdk` 0.1.x using your
  Pro/Max subscription, no API charges.

Telegram and Slack adapters compile and start; they auto-disable until you
provide tokens. The Windows installer (`install.bat` + `wizard.ps1`) is
checked in but has not been dry-run on a clean PC yet — that is Sprint 3.

## Status

**Alpha.** The plumbing works and the dashboard is usable. The product is
being polished. Star this repo to follow the road to v1.0
([ROADMAP.md](ROADMAP.md)).

## Built on the shoulders of

- [Anthropic Claude](https://www.anthropic.com/claude) & [Claude Code](https://github.com/anthropics/claude-code)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Next.js](https://nextjs.org), [shadcn/ui](https://ui.shadcn.com), [react-pixi](https://github.com/pixijs/pixi-react)

## License

MIT. Do whatever, just don't blame us.

---

Built by [Eduardo Moraga](https://github.com/eduardomoraga) ·
Inspired by [OpenClaw](https://docs.openclaw.ai), [Engram](https://github.com/cpacker/MemGPT),
and the daily friction of running 30 agents by hand.
