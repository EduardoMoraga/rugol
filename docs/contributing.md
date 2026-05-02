# Contributing

Thanks for considering it. Rogologo is small and we'd like to keep it lean.

## Ground rules

- One feature, one PR. Stack changes need an ADR first.
- Tests for any logic in `core/`. Visual changes can ship without unit tests
  but should include a screenshot in the PR description.
- Write commit messages in [Conventional Commits](https://www.conventionalcommits.org/).
- Bilingual is non-negotiable: every user-facing string ships in EN and ES.

## Local dev (no Docker)

```powershell
.\scripts\dev.ps1
```

This launches `uvicorn` on port 8000 and `next dev` on port 3000 with hot reload.
Requires Python 3.12 and Node 20 installed locally.

## Project structure

See [ARCHITECTURE.md](../ARCHITECTURE.md) for the full map.

```
core/         Python FastAPI backend
dashboard/    Next.js 15 frontend
docs/         Public docs and ADRs
installer/    Windows install wizard
scripts/      Dev helpers, seed scripts
tests/        pytest suite
```

## Picking work

- Issues labeled `good first issue` are scoped for a first-timer.
- Issues labeled `help wanted` are mid-size and have clear acceptance criteria.
- Anything labeled `architecture` or `breaking` should be discussed first.

## Code style

- Python: `ruff` + `mypy --strict`. CI enforces both.
- TypeScript: `tsc --noEmit` + `eslint`. CI enforces both.
- No comments that describe what the code does. Comments explain *why*.

## Reviewing PRs

Be kind. Be specific. If a change is hard to review, that's a smell — split it.
