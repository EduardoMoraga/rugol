---
name: rogologo-add-agent
description: Register a new agent in Rogologo — scaffold the .md, place it under agents/, and verify it appears in the dashboard.
---

# /rogologo-add-agent

## Arguments
- `name`: kebab-case agent name (e.g. `pricing-analyst`)
- `model`: `claude-opus-4-7` | `claude-sonnet-4-6` | `claude-haiku-4-5-20251001`
- `description`: one-sentence purpose

## Steps

1. Create `agents/<name>.md` with the standard frontmatter:
   ```
   ---
   name: <name>
   model: <model>
   description: <description>
   ---
   ```
2. Add a stubbed body inviting the user to flesh out persona + rules + output format.
3. The watcher detects the new file within `DISCOVERY_INTERVAL` seconds and
   upserts the row. Verify the dashboard shows the agent.
4. Suggest the next steps: enrich the body, schedule a recurring run,
   or invoke `/rogologo-self-improve` after a few real runs.

## Output

The path of the new file and a confirmation that the dashboard now lists it.
