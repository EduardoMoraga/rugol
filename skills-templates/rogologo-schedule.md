---
name: rogologo-schedule
description: Create or update a recurring schedule for an agent (cron expression + prompt).
---

# /rogologo-schedule

## Arguments
- `agent`: the agent's name
- `cron`: a valid 5-field cron expression in UTC (e.g. `0 9 * * 1` = Mondays 9am UTC)
- `prompt`: the message to dispatch each fire

## Steps

1. Resolve the agent by name (404 if not found).
2. POST `/api/schedules` with `{ agent_id, cron_expr, prompt, enabled: true }`.
3. The scheduler picks it up immediately; next fire is shown in the response.
4. Confirm to the user with a human-readable cadence (e.g. "every Monday at 9 AM UTC").

## Output

Schedule id and human-readable cadence string.
