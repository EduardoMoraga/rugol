# Screenshots

Captures used in the project README and the launch deck. Take all of them
against a fresh `pnpm dev` build at 1440 × 900 with the dark theme.

## Required for v0.1.0 release

| File | Page | What to capture |
|------|------|-----------------|
| `01-operations.png` | `/` | Stat cards + live feed + ant-farm preview, three agents running |
| `02-agents.png` | `/agents` | Six cards in the grid, search box typed, one card hovered |
| `03-run-detail.png` | `/runs/N` | Live streaming output mid-token, blinking cursor, tool-call list |
| `04-schedules.png` | `/schedules` | Form open with cron preset selected, one existing schedule below |
| `05-ant-farm.png` | `/ant-farm` | Eight ants on the hex grid, two green/running, one red/error |
| `06-ontology.png` | `/ontology` | Graph with ~12 nodes, edges visible, minimap in corner |
| `07-improvements.png` | `/improvements` | Coloured diff with three additions and two deletions |

## Recipe to seed the demo data

```powershell
# 1. Boot the stack
.\.venv\Scripts\python.exe -m uvicorn core.main:app
cd dashboard ; pnpm dev

# 2. Fire a couple of runs to populate state
curl -X POST http://localhost:8000/api/agents/4/run -H "Content-Type: application/json" `
  -d '{\"prompt\":\"List three things that went well this week.\"}'
curl -X POST http://localhost:8000/api/agents/2/run -H "Content-Type: application/json" `
  -d '{\"prompt\":\"Write tomorrow morning brief.\"}'

# 3. Seed the ontology with a few triples
curl -X POST http://localhost:8000/api/ontology/triples -H "Content-Type: application/json" `
  -d '{\"src\":\"Eduardo\",\"predicate\":\"works-on\",\"dst\":\"Rogologo\"}'
curl -X POST http://localhost:8000/api/ontology/triples -H "Content-Type: application/json" `
  -d '{\"src\":\"Rogologo\",\"predicate\":\"uses\",\"dst\":\"FastAPI\"}'
```

Save captures into this directory with the names above. The README references
them as `docs/screenshots/0X-*.png`.
