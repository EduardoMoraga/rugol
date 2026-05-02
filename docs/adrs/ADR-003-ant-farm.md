# ADR-003 — The ant-farm visualization

**Status:** Accepted · 2026-05-02 · Author: rogologo-architect

## Context

A list of cards is functional but boring. Several recent agentic tools
(Stanford Smallville, AI Town, BabyAGI dashboards) showed that **giving
agents a visual body** turns a debugging panel into something users want
to watch.

Eduardo's brief was explicit: "ideal que tenga monitos en 2D algo feo
jajaja pero útil. Por ver a mis agentes trabajar."

We need a visualization that is:

- Cheap to render (must run on a 5-year-old laptop without fans spinning)
- Communicative (status, recency, business activity at a glance)
- Optional (advanced users may disable it for a denser data view)
- Distinctive (this is the screenshot people share on social media)

## Decision

Render an **ant-farm**: a 2D scene where each registered agent is a sprite,
laid out on an auto-sized hex grid. State drives sprite & animation:

| Agent state | Sprite | Behavior |
|---|---|---|
| `idle` | gray ant, slow blink | random wander inside its tile |
| `running` | green ant, antennae moving | walks toward a "task" icon, drags it back |
| `error` | red ant, shaking | static, exclamation mark above |
| `offline` | semi-transparent | crossed out |

Stack:

- **PixiJS v8** via **`@pixi/react`** — WebGL renderer, 60 fps with hundreds
  of sprites, mature ecosystem.
- **Sprite assets**: hand-pixeled 32×32 PNGs in 4 frames each. Bundled in
  `dashboard/public/sprites/ants/`.
- **State source**: subscribed to the same SSE stream as the rest of the
  dashboard; reconciles by `agent_id`.
- **Interaction**: hover → tooltip; click → opens the agent's detail panel.

A toggle in settings hides the canvas for users who prefer raw cards.

## Consequences

- **Positive:** Distinctive identity. The ant-farm is what people will
  remember and screenshot.
- **Positive:** Cheap to extend — new sprite states (e.g., "self-improving",
  "asking for permission") are 4 frames of art away.
- **Negative:** A WebGL canvas costs more memory than HTML cards. We mitigate
  by capping sprite count to 100 (after that, cards-only mode kicks in).
- **Negative:** Pixel art has to be drawn. We start with 1 ant skin shared
  across all agents; per-role skins (analyst / writer / scraper) are a v2
  delight feature.

## Alternatives rejected

- **3D scene (Three.js)**: too heavy, no clear comprehension benefit.
- **Force graph (react-force-graph)**: better suited to relationships, not
  to "is this agent busy right now".
- **A literal Slack-like timeline**: useful, but already covered by the
  run history panel. The ant-farm earns its space by doing what cards
  cannot — making activity *felt*.
