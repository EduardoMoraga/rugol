# ADR-005 — Project-first model

**Status:** Accepted · 2026-05-03 · Author: rugol-architect (paradigm shift requested by Eduardo Moraga)

## Context

Rugol until v0.3 modeled the world as a flat list of **agents**. The dashboard
home was a list of agents, the Architect produced agents, the ontology lived
globally, schedules pointed at agents. This is what every other agent platform
does today.

The product owner observed — correctly — that this is the wrong unit of
account for the audience we want to reach. **People do not think in agents.
People think in projects.** A project is a piece of life or work that has a
goal, a team, a cadence, and a memory. Agents are the staff the project
relies on. The human sets the direction and keeps every decision; the
agents do the work and surface a second perspective.

Examples the user gave that drove the change:

- *"Asistente personal"* — a project whose team manages calendar, inbox,
  travel, finances. The user does not want to think about which agent runs
  which slice — they want to ask the project a question.
- *"Mi hija aprende biología"* — a project that produces educational games
  and quizzes. The team is small (a content writer, a game designer) but
  the *purpose* is what gives meaning.
- *"Marca personal"* — brand-architect, content-editor, market-analyst,
  cold-prospector — clearly a department, not four lonely agents.
- *"Pipeline comercial Increxa"* — a project mirroring an actual business
  workflow.

This ADR rebuilds the data model and navigation around **Project** as the
primary entity.

## Decision

### Schema

A new top-level table `projects`:

| column        | type        | notes |
|---------------|-------------|-------|
| id            | integer PK  | |
| slug          | text unique | url-safe, derived from name on creation |
| name          | text        | "Marca personal" |
| description   | text        | one-line for cards |
| mission       | text        | several lines — the "why" the team reads at every run |
| color         | text        | hex, used to color cards and agent badges |
| icon          | text        | lucide icon name (Briefcase, Sparkles, Heart, Rocket…) |
| status        | text        | `active`, `archived` |
| created_at    | datetime    | |
| updated_at    | datetime    | |

`agents.project_id` is added as a **nullable** FK to `projects.id` with
`ON DELETE SET NULL`. Nullable on purpose: agents can momentarily have no
project (during reassignment, during seed) without breaking integrity.

### Backfill

On startup, after `Base.metadata.create_all`:

1. If no project exists, create the **Workspace** project
   (slug=`workspace`, icon=`briefcase`, color=`#7280a8`). This is the catch-all
   for everything pre-migration.
2. Any agent with `project_id IS NULL` is assigned to Workspace.

This is non-destructive and idempotent. A returning user sees their existing
agents under Workspace, then can move them or create new projects.

### Frontmatter

Agent `.md` files gain an optional `project:` field:

```yaml
---
name: brand-architect
model: claude-opus-4-7
project: marca-personal      # optional; defaults to "workspace"
description: "..."
---
```

If the slug is unknown at load time, the loader **does not invent** the
project — it falls back to Workspace and emits a warning. Project creation
is an explicit user action (not a side effect of dropping a file).

### API surface

- `GET    /api/projects`               → list with agent_count, run_count_24h
- `POST   /api/projects`               → `{name, description, mission, color, icon}`
- `GET    /api/projects/{id_or_slug}`  → detail with agents + recent runs
- `PATCH  /api/projects/{id_or_slug}`  → edit
- `POST   /api/projects/{id_or_slug}/move-agent` → `{agent_id}` reassigns
- `DELETE /api/projects/{id_or_slug}`  → 409 if it still has agents

### Architect integration

`Proposal` gains a `project` block:

```json
{
  "project": {
    "mode": "create" | "use_existing",
    "id_or_slug": null | "marca-personal",
    "name": "Marca personal",
    "mission": "..."
  },
  "agents": [...],
  ...
}
```

The deployer:
- if `mode=create`, creates the project (or reuses if slug exists)
- writes `project: <slug>` into each agent `.md`
- assigns `project_id` on every upserted agent row

The Architect prompt is updated to *always* propose a project name and mission
together with the team. A team of agents without a project is a smell.

### Navigation

- New top entry **Projects** at the top of the nav rail (replaces Operations
  as default home).
- `/` redirects to `/projects`.
- `/operations` keeps the system-wide live view (stays useful for power users).
- Agent cards everywhere show a small project badge (color + icon).

### Why this matters for the product

Projects give us a natural surface for the behavioral-economics commitments
in `MANIFESTO.md`:

- **Mission per project** = the "why" agents read before each run, reducing
  noise (Kahneman/Sunstein) by anchoring decisions in shared intent.
- **Per-project memory & biases** = the unit at which the self-improving
  loop accumulates (an `inbox-watcher` for marca-personal vs one for
  hija-aprende should not pollute each other's lessons).
- **Per-project data scope** = a future Capa lets each project declare what
  data it touches (Calendar, Email, Drive). Approval lives at project
  granularity because that's the unit the user mentally reasons about.

## Consequences

- **Positive:** the home page becomes meaningful immediately — the user
  sees a list of departments, not a list of files.
- **Positive:** the Architect now produces a coherent department, not
  scattered agents. The "what is this for?" question gets a real answer.
- **Positive:** opens the door to per-project memory, per-project
  permissions, per-project teams.
- **Negative:** every page that listed agents needs a project filter and
  a badge. We accept the UI surface cost.
- **Negative:** users without projects in their head (true power users
  who want flat agents) need to live with the "Workspace" bucket. We
  judge this fine — they can always create one project per agent.

## Alternatives rejected

- **Tags** instead of a Project entity: rejected — tags don't carry
  mission, color, status, or settings. Mental model stays weak.
- **Folders on disk** as projects: tempting but couples filesystem layout
  to product semantics; users want to drop `.md` anywhere. Slug field
  in frontmatter is loose enough.
- **No backfill, fresh start**: rejected — destroys returning-user data.
