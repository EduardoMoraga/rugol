# rogologo-backend — memoria

## Aprendizajes del scaffolding inicial (2026-05-02)

- `claude-agent-sdk` Python esperar `cwd` del workspace, `permission_mode="bypassPermissions"`,
  `setting_sources=["user","project","local"]` para heredar `.claude/agents/` y MCPs.
- Para subscription auth: remover `ANTHROPIC_API_KEY` y `ANTHROPIC_AUTH_TOKEN` del env del subprocess.
- `ResultMessage` trae `usage.input_tokens`, `usage.output_tokens`, `total_cost_usd`, `session_id`.
- SSE con `sse-starlette`: usar `EventSourceResponse`, heartbeat cada 15s para no perder conexión por proxies.
- APScheduler con jobstore SQLite separado (`data/scheduler.db`) — evita lock contention con el DB principal.
- `python-telegram-bot` v21+ requiere `await app.initialize() / start() / updater.start_polling()` para iniciar polling sin bloquear.
- `slack_bolt.async_app.AsyncApp` + `AsyncSocketModeHandler` para socket mode (no necesita exponer webhook público).
- watchdog `Observer` se debe correr en su propio thread; comunicar via `loop.call_soon_threadsafe` o `asyncio.run_coroutine_threadsafe`.

## Patrones que valieron la pena

- Bus in-process (`fnmatch` patterns) → fácil de migrar a Redis pub/sub después.
- `RunRequest` dataclass → desacopla orquestador del trigger (schedule, telegram, slack, dashboard, api).
- `body_hash` (sha256) → comparar antes de escribir DB, evita updates ruidosos.
- Modelos SQLAlchemy 2.0 con `Mapped[...]` y `mapped_column` → más limpio y typecheck-friendly.

## Pendientes técnicos (Sprint 1)

- [ ] `core/db/migrations/` con Alembic (hoy uso `init_db()` para dev).
- [ ] Reusar `ProgressEditor` de eduagent-gateway en el adaptador Telegram.
- [ ] Tests con pytest-asyncio que mockeen el subprocess `claude`.
- [ ] Error tipado: `RogologoError` base, `AgentNotFound`, `RateLimitExceeded`, etc.
- [ ] Adapter común con `Adapter.publish()` que reciba run_id y rutee al canal correcto.
