# Security policy

## Reporting

If you find a vulnerability, please email **security@rogologo.dev** with the
following:

- A clear description of the issue
- Reproduction steps or PoC
- Affected version(s)
- Your name (or pseudonym) for credit, if you want it

We will acknowledge within 72 hours and aim to ship a patch within 14 days
for high-severity issues.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.x     | Yes — current |

Once 1.0 ships, we will support the latest minor and the previous one.

## Threat model

Rogologo is designed for single-user, single-host deployment. Out of scope for
the threat model:

- Multi-tenant isolation
- Sandbox escape from the `claude` subprocess (we run with `bypassPermissions`
  on purpose; the operator is trusted)
- Compromise of the host OS

In scope:

- Token leakage via logs, error responses, or telemetry
- Unauthorized access to the dashboard or API from another user on the same machine
- Unauthorized message dispatch via the Telegram or Slack adapters

## Hardening checklist for production

- Run on a host you control; don't expose port 3000 or 8000 to the public internet
  without an authenticating reverse proxy.
- Use the `prod` Docker profile (Postgres + Redis); set strong `POSTGRES_PASSWORD`.
- Rotate `SESSION_SECRET` periodically.
- Keep your Telegram allowlist tight. Never run with an empty allowlist.
- Limit `MAX_CONCURRENT_RUNS` to avoid runaway costs.
- Subscribe to GitHub release notifications for security patches.
