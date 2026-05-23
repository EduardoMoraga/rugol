---
name: rogologo-import-project
description: Import an existing Moragent project (.claude/agents, .claude/skills, .claude/agent-memory) into this Rogologo install in one command.
---

# /rogologo-import-project

Use when bringing a project built with Moragent (e.g. `hro-v2`, `philips-bi`) into a fresh or existing Rogologo install. Copies agents, skills and per-agent memory from the project's `.claude/` folder into the Rogologo workspace where the filesystem watcher will pick them up.

## Arguments

- `source`: absolute path to the Moragent project folder (the one that contains `.claude/`).
- `--apply`: actually copy. Without it the script runs in dry-run mode and only previews changes.
- `--overwrite`: replace files/folders that already exist in the Rogologo install. Default is skip.

## What it does

1. Reads `<source>/.claude/agents/*.md`, `<source>/.claude/skills/*.md`, and each subfolder of `<source>/.claude/agent-memory/`.
2. Plans the copy into `agents/`, `skills/`, and `agent-memory/` under the Rogologo install root.
3. Dry-run prints a table grouped by kind (agent / skill / memory) and action (copy / skip / overwrite). Nothing is written.
4. With `--apply`, performs the copy. The watcher registers the new files within `DISCOVERY_INTERVAL` seconds (default 5).

## How to run

From the Rogologo install root:

```powershell
# 1. Preview
python scripts/import_project.py --source "C:\Moragent\01-INCREXA\clientes\hro-v2"

# 2. Apply
python scripts/import_project.py --source "C:\Moragent\01-INCREXA\clientes\hro-v2" --apply

# 3. Re-run after the source project changes (replace existing copies)
python scripts/import_project.py --source "C:\Moragent\01-INCREXA\clientes\hro-v2" --apply --overwrite
```

On Linux / VM:

```bash
python3 scripts/import_project.py --source /mnt/hro-v2 --apply
```

## After import

- Open `http://localhost:3000` — the new agents appear in the Agents list within seconds.
- From Telegram, message the bot:
  ```
  /bind <agent-name>
  ```
  to bind your chat to one of the imported agents (e.g. `/bind hr-cv-screener`).
- Imported skills are available to every agent that runs in this Rogologo workspace.

## What is NOT imported

- The project's `CLAUDE.md` (would clash with Rogologo's own).
- Anything outside `.claude/` (data files, scripts, templates of the source project stay where they are).
- Secrets — `.env` and credentials are never touched.

## Output

- Dry-run: a table of planned operations plus a per-kind summary.
- Apply mode: the number of items written and a reminder that the watcher will auto-register them.
