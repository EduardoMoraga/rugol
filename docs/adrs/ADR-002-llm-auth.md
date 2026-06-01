# ADR-002 — LLM auth: subscription vs API

**Status:** Accepted · 2026-05-02 · Author: rugol-architect

## Context

Most demo users will not have Anthropic API credits. They will have a
**Claude Pro or Max subscription**, which can be unlocked from local processes
via `claude /login` (OAuth flow handled by the Claude Code CLI).

For production / high-concurrency / CI use cases, an API key is more
appropriate: no rate limits per user, deterministic billing, no OAuth
expiration to babysit.

We need a single architecture that supports both, without code branches in
the runner.

## Decision

The runner **always** spawns a `claude` CLI subprocess. The `.env` flag
`USE_SUBSCRIPTION` chooses the auth path:

```python
def build_env() -> dict[str, str]:
    env = dict(os.environ)
    if settings.USE_SUBSCRIPTION:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    else:
        env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
    return env
```

When `USE_SUBSCRIPTION=true`, the CLI falls back to its OAuth-stored token,
which the user installed via `claude /login` during the installer wizard.

When `USE_SUBSCRIPTION=false`, the CLI uses the env var directly.

The runner does not call `anthropic.Anthropic` directly. Going through the CLI
gives us:

- Free access to the agent SDK's session/resume mechanics
- The same subagent / skill / MCP wiring as Claude Code
- A single execution path identical to a developer's local terminal

## Consequences

- **Positive:** The same Rugol binary serves a hobbyist on Pro and a team
  on the API.
- **Positive:** Setup wizard can default to "use my subscription, no charges"
  which removes the API-billing barrier for first-time users.
- **Negative:** Concurrency on subscription is rate-limited (Pro: ~5
  concurrent, Max: ~20). We expose `MAX_CONCURRENT_RUNS` so the operator
  can tune it. The scheduler queues excess runs.
- **Negative:** The `claude` CLI must be installed in the container, which
  means our backend image bundles Node 20 alongside Python 3.12.
  Image size grows by ~150 MB; acceptable.

## Alternatives rejected

- **Anthropic Python SDK direct**: simpler image, but loses the SDK runtime's
  session/resume + subagent + skill loading. We would re-implement those.
- **OpenRouter / proxy**: would let us pretend any LLM works, but Rugol
  is a Claude-first product on purpose. v2 may add a generic adapter.
