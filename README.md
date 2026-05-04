<div align="center">

# Rogologo

**Your AI agent operating system, made for people who think in projects, not in tech.**

A local control room where teams of Claude agents work for you — your brand,
your daily life, helping your kid study, your sales pipeline.

[Quickstart](#quickstart) · [Why Rogologo](#why-rogologo) · [Real cases](#real-cases) · [How it works](#how-it-works) · [Español](README.es.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

> **"Life is the sum of projects. You're the CEO; they execute."**

Rogologo flips the paradigm. You don't think "what agent should I create".
You think **what project do I need**: a personal assistant, your brand,
helping your daughter learn biology through games, your sales pipeline.
Each project comes with its own team of specialist agents, its written
mission, and its living rules. You're the project's CEO; the agents are
the department.

---

## Why Rogologo

### Built by a business person, not a dev

I'm an economist. I lead Business Intelligence projects across LATAM. I
watched "agentic AI" get trapped in technical jargon that excludes the
very people the tool can change life for.

Rogologo was born from that frustration. Behind the code (which I wrote
with Claude Code, naturally), the product decisions come from a
different place: **behavioral economics, real productivity problems,
everyday life**.

### The project-first paradigm

| Other platforms | Rogologo |
|---|---|
| Flat list of standalone agents | Projects as departments with mission |
| You pick the model (haiku/sonnet/opus) | You pick the **task type** (heuristic / think / deliberate); the system routes |
| Agent acts alone | Optional: devil's advocate challenges before acting |
| Memory per-agent or none | Living lessons per project — every team member reads them before each task |
| Technical templates | Emotional templates: "personal assistant", "my daughter learns through games" |

### Three behavioral economics principles, embodied in software

| Principle | How it shows up in Rogologo |
|---|---|
| **System 1 vs System 2** (Kahneman) | The user doesn't think in models. They pick *Heuristic* (haiku, fast), *Think* (agent's model) or *Deliberate* (opus, hard-to-reverse decisions). |
| **Noise** (Kahneman/Sunstein) | Before important decisions, "Devil's advocate" (opus) challenges the primary answer. Two perspectives, you decide. |
| **Biases** | Each project keeps a living list of *lessons* (lesson / bias / fact). Every team member reads it before each run. What you learned the hard way becomes a permanent anchor. |

---

## Real cases

### "My daughter learns through games"

My 9-year-old had a biology test. In 5 minutes, two agents (designer
Haiku + builder Sonnet) generated an HTML+JS mini-game about
photosynthesis. No libraries, no install, double-click and play. She
learned without realizing it. She studied while laughing.

It's a built-in template. A mom who's only ever used ChatGPT can clone
it, write "this week's topic is cells", and get a fresh game in minutes.

### "My personal brand"

Three agents that take care of public voice: brand-architect (Opus,
decides what's on-brand), content-editor (writes the posts),
market-analyst (measures what resonates). Living lessons like *"never
say 'leverage'"* or *"zero hype"* get injected into every run, so the
team doesn't drift even when you're not watching.

### "Sales pipeline"

For freelancers and founders who run sales in a spreadsheet:
prospector + qualifier + follower-upper. Daily schedule that drops no
active follow-up. Honesty about fit: if we're not the right vendor,
the system says so.

### "Personal assistant"

Morning brief, inbox triage, end-of-day capture. The invisible team
that takes care of your day.

### "Topic researcher"

When you need to master something new in a week: researcher gathers
sources, explainer translates them into everyday analogies, critic
challenges the consensus. Takes you from 0 to being able to hold an
informed conversation.

---

## How it works

Three concepts. That's it.

### 1. Project = department with a mission

Each project has a name, a color, an icon, a written mission (the why),
and a 1-5 agent team. Every team member reads the mission **before each
task** — it's an anchor against drift.

### 2. Living lessons

When the team learns something (a bias spotted, a decision made, a
business rule), you add it as a lesson to the project. Next time any
team member works, they'll read it. The project's memory grows without
anyone losing context.

Every assistant answer and every devil's advocate critique exposes a
**"Promote to lesson"** button — one click and that learning becomes a
permanent anchor.

### 3. Task type + devil's advocate

Above each chat input:

- **Heuristic** → routed to haiku, fast and cheap.
- **Think** → agent's own model, the default.
- **Deliberate** → routed to opus, deep reasoning.

And a **"Request devil's advocate"** checkbox: after the answer, a
second agent (opus) challenges it specifically. Two perspectives for
the decisions that matter.

---

## Quickstart

**Prerequisites**: Windows 10/11 (Mac/Linux work, installers in
progress), Python 3.12+, Node 20+, Docker optional, and `claude /login`
done once for auth.

```bash
# Clone
git clone https://github.com/<your-fork>/rogologo.git
cd rogologo

# Backend (Python venv)
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # PowerShell
# source .venv/bin/activate     # bash
pip install -r core/requirements.txt
cp .env.example .env             # set USE_SUBSCRIPTION=true if you have Pro/Max
uvicorn core.main:app --host 127.0.0.1 --port 8000

# Frontend (separate terminal)
cd dashboard
pnpm install
pnpm dev
```

Open `http://localhost:3000`. If it's your first time, you'll see an
emotional landing screen with five ready-to-clone templates. Click one
→ tweak if you want → deploy. Your team is up and running.

---

## What's already inside · `v0.5.0-alpha`

Rogologo was built in layers, each shipped as a working, tested commit.
The current version includes:

| Capa | What it adds |
|------|---------------|
| **1** | Project-first model, non-destructive migration, /projects as home |
| **2** | Multi-turn chat with cross-turn memory, clickable markdown + syntax highlight |
| **3** | Living lessons per project + auto self-improvement trigger (Hermes-style) |
| **4** | System 1/2 (task type selector) + optional devil's advocate |
| **5** | Per-agent tool whitelist + Architect dir picker |
| **6** | 5 curated project templates, one-click clone, auto-rename for duplicates |
| **7** | "Promote to lesson" everywhere — chat, advocate critiques, self-improvements |
| **8** | Per-agent MCP servers (stdio/sse/http) — connect Asana, Notion, Slack per agent |
| **9** | Ant farm with project clusters (visualization) |
| **10** | Emotional first-time onboarding |
| **11** | Extended health check + DEVELOPMENT.md |
| **13** | Telegram + Slack adapters with channel bindings + reply-on-completion |
| **14** | Reset to clean state (script + admin endpoint + Settings button) — install on a new PC in minutes |
| **15** | EN/ES toggle in the nav rail (persisted in localStorage) |

Full history in [CHANGELOG.md](CHANGELOG.md). Technical detail in
[DEVELOPMENT.md](DEVELOPMENT.md) and the ADRs at [`docs/adrs/`](docs/adrs/).
To install on a fresh PC see [docs/install-on-new-pc.md](docs/install-on-new-pc.md).

---

## Stack

- **Backend**: Python 3.12, FastAPI, async SQLAlchemy, SQLite (Postgres
  optional), APScheduler, claude-agent-sdk.
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS v4, react-query,
  react-markdown, HTML5 Canvas for the ant farm.
- **LLM auth**: Claude Pro/Max subscription **or** API key — your call,
  per project.
- **Local-first**: everything runs on your machine. No telemetry by default.

---

## For developers

If you're contributing or forking, read [**DEVELOPMENT.md**](DEVELOPMENT.md)
first. It captures the stack, migration rules, known bugs (with tested
workarounds), an architecture cheatsheet, and a map of which file
implements which Capa.

Pull requests welcome. Issues with real use-cases (especially from
non-technical people) are even more welcome — they're the material that
tells us which template is missing.

---

## Next on the roadmap

- **Capa 8** — Per-agent MCP servers (connect Asana, Notion, Slack,
  Gmail per agent without touching the global .env).
- **Telegram + Slack adapters** — chat with any agent from your phone,
  with the adapter wired per-project.
- **Additional Spanish templates** — *"My restaurant business"*,
  *"Customer support for my online store"*, more LATAM cases.
- **Windows `.bat` installer** — one line for zero-code users.

---

## License

MIT. Do what you need.

---

<div align="center">

Crafted by **Eduardo Moraga** ([eduardo.moraga.o@gmail.com](mailto:eduardo.moraga.o@gmail.com))
— economist, BI lead at Increxa, AI public speaker in LATAM.

If this helped you, tell me what project you used it for. That's what
moves the roadmap.

</div>
