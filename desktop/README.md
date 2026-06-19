# Rugol — suite de escritorio (Rugol · Rugol CRM · Rugol HRO)

Tres apps de escritorio macOS, autocontenidas (traen Python + Node + el CLI de Claude
embebidos). No requieren terminal, ni Docker, ni instalar nada aparte. Cada una es la
misma plataforma agéntica **Rugol** (FastAPI + dashboard Next), pre-sembrada y branded
para su dominio.

| App | Para qué | Acento | Flota |
|-----|----------|--------|-------|
| **Rugol** | Plataforma general de agentes | terracota | Architect, agentes (Soul/Memory/Tools/MCP), Ontología, self-improving |
| **Rugol CRM** | Prospección B2B | teal | hunter · researcher · closer · strategist · icp-designer → tablero **Prospectos** |
| **Rugol HRO** | Reclutamiento | violeta | screener · **Sofía** (voz) · matcher · knockout · offer → **Candidatos + Entrevistas** |

Auth: inicias sesión con tu **cuenta de Anthropic** (suscripción Pro/Max/Team) o una API key.

---

## Rugol HRO — el flujo de reclutamiento

```
  Pandapé / link            hro-screener            Sofía (voz, ElevenLabs)         Rugol                 hro-matcher
  ───────────────  ──►  ─────────────────────  ──►  ─────────────────────────  ──►  ───────────────  ──►  ───────────
  Llega el CV o le       Evalúa el CV vs el           Entrevista por voz por          Trae la entrevista,    Compara y arma
  compartes el link      perfil y recomienda          6 competencias (BARS),          la puntúa y crea el    la terna (top 3)
  de entrevista          entrevistar                  con evidencia citada            candidato en el        recomendada
                                                                                       pipeline (auto)
```

### El link que compartes para la entrevista
`https://hro-entrevista.vercel.app/` — se lo mandas al candidato (WhatsApp/email). Abre la
landing de Sofía y hace la entrevista por voz. Dentro de la app: **Entrevistas → "Lanzar
entrevista de voz"** lo abre; al terminar, **"Sincronizar con ElevenLabs"** (o el sync
automático cada 5 min) la trae puntuada.

### Dónde se configura cada herramienta
| Herramienta | Para qué | Dónde |
|-------------|----------|-------|
| Cuenta Anthropic | Cerebro de los agentes | Onboarding al abrir la app |
| ElevenLabs (Sofía) | La voz de la entrevista | **Settings → "Entrevistas por voz · Sofía"** (API key + Agent ID) |
| Telegram | Hablarle a los agentes por chat | **Settings → Telegram** (pega el token; sin User ID, sin /bind) |
| Herramientas por agente (MCP) | Conectar Asana/Notion/etc. a UN agente | **Agentes → abrir agente → Tools / MCP** |
| Pandapé (CV intake) | Importar candidatos del ATS | *(próximo)* |

### Dónde ves cada cosa
- **Candidatos** — kanban del embudo (Postulado → … → Contratado).
- **Entrevistas** — entrevistas de Sofía: 6 competencias BARS + evidencia + veredicto.
- **Agentes → hro-sofia → Edit spec** — configurar qué pregunta Sofía (se adapta por posición).
- **Settings** — cuenta, ElevenLabs, Telegram.

---

## Desarrollo / build

```bash
# Dashboard (una sola vez por cambio de UI)
cd dashboard && pnpm build
cp -R .next/static .next/standalone/.next/static && cp -R public .next/standalone/public
# (el payload se rearma con build-variant.sh)

# Empaquetar una variante (rugol|crm|hro) → release-<v>/*.dmg
cd desktop && ./build-variant.sh hro
```

El payload (`desktop/build-payload/`, gitignored, ~775MB) trae: `python/` (intérprete
relocatable + deps), `node/` (para el dashboard), `dashboard/` (build standalone) y
`rugol-src/` (backend + templates de la variante). `main.cjs` levanta backend + dashboard
detrás de un reverse-proxy in-process y carga la ventana.
