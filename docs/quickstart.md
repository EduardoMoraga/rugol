# Quickstart

> Get Rugol running on a fresh Windows PC in under 10 minutes.

## 1. Download

```powershell
git clone https://github.com/eduardomoraga/rugol.git
cd rugol
```

If you don't have Git, download a ZIP from the [latest release](https://github.com/eduardomoraga/rugol/releases).

## 2. Run the wizard

```powershell
.\installer\install.bat
```

The wizard will:

1. Verify Docker Desktop, Node.js 20+, and the Claude Code CLI are installed.
   It points you to the install pages for any that are missing.
2. Walk you through `claude /login` if you want to use your Pro/Max subscription
   (no API charges). Alternatively, you can paste an API key.
3. Optionally collect a **Telegram bot token** and **Slack tokens** so you can
   chat with your agents from your phone or workspace.
4. Write `.env` with sensible defaults and a fresh session secret.
5. Build & launch the Docker stack.
6. Open the dashboard at <http://localhost:3000>.

## 3. Add your first agent

Drop any markdown file with frontmatter into `agents/`:

```markdown
---
name: brand-architect
model: claude-opus-4-7
description: Posts to LinkedIn every Monday with curated takes.
---

You are a personal-brand strategist for Eduardo. Each Monday at 9 AM you
review what he published last week and propose three post variants.
```

Within seconds you'll see the agent appear in the dashboard. Click "Run" to
test it. Add a schedule from the agent detail page.

## 4. Connect Telegram (optional)

If you provided a bot token, send any message to your bot. It dispatches the
text to the default agent and replies with the result. To bind multiple agents
to a single channel ("teams"), see [Teams](teams.md) (post-Sprint 4).

## 5. Watch the ant farm

Click "Ant farm" in the sidebar. Each ant is one of your agents. Green = working,
gray = idle, red = errored. The colony grows as you add agents.

## Common issues

- **Docker says it can't find an image** — the first `compose up` builds them
  locally; that takes 3-5 minutes. Subsequent runs are instant.
- **Telegram says "Conflict"** — you have another bot poller running with the
  same token (a leftover process). `taskkill /F /IM python.exe` and retry.
- **Dashboard is blank** — open the browser console; if you see CORS errors,
  make sure `NEXT_PUBLIC_API_URL` in `.env` matches the URL you're using.

For more, see [Troubleshooting](troubleshooting.md).

## Local development (without the installer)

If you'd rather run the two services directly on your host (faster iteration
than rebuilding Docker images), here is the verified flow:

```powershell
# 1. Backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r core\requirements.txt
copy .env.example .env   # or write your own; AGENTS_DIR defaults to agents-templates\
.\.venv\Scripts\python.exe -m uvicorn core.main:app --host 127.0.0.1 --port 8000

# 2. Dashboard (in a second terminal)
cd dashboard
pnpm install
pnpm dev
```

Open <http://localhost:3000>. The four bundled templates appear under
**Agents**; clicking **Run** on the `maintenance` agent fires a real
`claude-agent-sdk` invocation and persists tokens/cost.

Smoke-test endpoints:

```powershell
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/agents
curl -X POST http://127.0.0.1:8000/api/agents/4/run `
  -H "Content-Type: application/json" `
  -d '{\"prompt\":\"Reply with the single word: pong\"}'
curl http://127.0.0.1:8000/api/runs/1
```
