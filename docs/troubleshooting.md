# Troubleshooting

## "Docker says it can't find an image"

The first `docker compose up` builds the images locally; it takes 3-5 minutes.
Subsequent runs are instant. If the build fails:

```powershell
docker compose logs core
docker compose logs dashboard
```

## Dashboard is blank

Open the browser console. If you see CORS or 502 errors:

1. Check `docker compose ps` — are both containers up and healthy?
2. Check `NEXT_PUBLIC_API_URL` in `.env` matches the URL you're using.
3. Restart the stack: `docker compose down && docker compose up -d`.

## Telegram says "Conflict: terminated by other getUpdates request"

You have another bot poller running with the same token. Common causes:

- A leftover `python.exe` from a previous test of `eduagent-gateway`.
- The bot is also polling somewhere else (another machine, a hosted instance).

```powershell
Get-Process python -ErrorAction SilentlyContinue
taskkill /F /IM python.exe
docker compose restart core
```

## My agent runs but doesn't seem to do anything

1. Check `docker compose logs core` for errors during the run.
2. Check the agent's `.md` file — does the frontmatter have a valid `name` and `model`?
3. Trigger a run manually from the dashboard and watch the SSE feed.
4. If the run completes without text output, the agent's prompt may be too narrow.

## My subscription is rate-limiting me

Set `MAX_CONCURRENT_RUNS=1` in `.env` and restart. If you need more concurrency,
switch to API mode (`USE_SUBSCRIPTION=false` and `ANTHROPIC_API_KEY=sk-ant-...`).

## I edited an agent's `.md` and the dashboard hasn't updated

The watcher debounces by 200ms and the dashboard polls every 5s. Wait 10 seconds.
If still stuck, restart the core service.

## I want to wipe everything and start over

```powershell
docker compose down -v
Remove-Item -Recurse -Force data, logs
.\installer\install.bat
```
