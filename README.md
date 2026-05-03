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

## The Architect

OpenClaw and similar gateways give you a great 1:1 chat with one agent. They
do not design the team you actually need.

Rogologo's `/architect` does. You type a one-line outcome ("draft three
LinkedIn posts every Monday from what I shipped"), and a meta-prompted Claude
returns a complete, editable proposal:

- **The agents** (1–5, each with a sharp role, model choice, and 200–600 word
  prompt body)
- **The skills** they share (only when reuse justifies a separate file)
- **The schedules** that drive the cadence (UTC cron expressions)
- **The ontology seeds** that connect them

You review every piece in editable cards, drop the ones you do not want,
tweak names and prompts, and click **Deploy**. Rogologo writes the markdown
files, registers the schedules, seeds the ontology — all on disk, all
inspectable. Nothing is overwritten silently.

This is the difference. Rogologo is **the conversation that turns "I have
an idea" into a running fleet of agents**, not a chat window.

> Pairs naturally with [Moragent](../../00-CORE/skills/moragent.md), the
> Claude Code skill for hand-designing agentic infrastructure inside a
> Claude Code session. Use Architect when you want the design done for you;
> use Moragent when you want to drive the design yourself. Both produce the
> same `.md` format Rogologo runs.

## What works today (v0.3.0-alpha)

Verified end-to-end on Windows 11 + Python 3.12 + Node 20:

- ✓ **Describe an idea, get a proposal**: `/architect` returns 1–5 agents,
  skills, schedules, and ontology seeds in 15–40 seconds. Every piece is
  editable inline before deploy.
- ✓ **One-click deploy of the proposal**: writes the markdown files, creates
  the schedules, seeds the ontology. Existing files never overwritten.
- ✓ **Agent detail with tabs**: Overview / Spec / Memory / Tools — see who
  the agent is, what it knows, and what it can use.
- ✓ **Skills page** lists every reusable capability with full spec dialog.
- ✓ **Create an agent from the dashboard** (no terminal): name, model,
  description, prompt body — Rogologo writes the `.md` into your agents
  folder and registers it.
- ✓ **Edit any agent's spec** from `/agents/<id>/edit` and save; the watcher
  reloads it.
- ✓ **Drop a `.md` from elsewhere** into your AGENTS_DIR — it lands in the
  dashboard within 5 seconds (debounced watchdog).
- ✓ Click **Run**, type a prompt, get redirected to a live `/runs/[id]` page
  that streams the assistant's output token-by-token, shows tool calls as
  they happen, and persists the final text + token cost + session id to SQLite.
- ✓ Create a recurring schedule with a cron expression; the job survives
  restart (APScheduler SQLite jobstore).
- ✓ **Paste your Telegram bot token + allowed user IDs into `/settings` and
  hit Save**. The bot starts polling immediately. No backend restart, no
  `.env` editing.
- ✓ Same for **Slack** (bot token + app-level token + signing secret) — saves
  trigger a hot restart of the socket-mode handler.
- ✓ Switch the **agents folder** from `/settings` to point at your real
  `.claude/agents/` and the watcher rescans on the spot.
- ✓ Browse the **ontology** as an interactive graph (typed nodes, labelled
  predicate edges, minimap, pan/zoom).
- ✓ Review **self-improvement** proposals on a tabbed page with a
  syntax-coloured diff viewer; every change requires explicit approval.
- ✓ Persistent **activity feed** in the operations page tells you what the
  fleet is doing, in real time.
- ✓ The bundled `claude` CLI is invoked via `claude-agent-sdk` 0.1.x using
  your Pro/Max subscription, no API charges.

The Windows installer (`install.bat` + `wizard.ps1`) is checked in but has not
been dry-run on a clean PC yet — that is the next sprint.

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
