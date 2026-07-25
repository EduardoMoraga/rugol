# Rugol v0.6 — Roadmap

> Capturado en sesión 2026-05-05 después de instalar Rugol desde cero
> en un PC Windows 11 limpio + intentar replicar el equipo Gugol que
> Eduardo Moraga ya tiene operativo en OpenClaw.
>
> Esta sesión dejó al descubierto bugs reales, gaps de UX que separan a
> Rugol de "herramienta para humanos no técnicos", y un mapa concreto
> de skills pendientes para alcanzar paridad con OpenClaw.

---

## Hot fixes incluidos en este commit

### 1. `aiohttp` faltaba en `core/requirements.txt`

**Síntoma**: el adapter de Slack reportaba `slack-bolt not installed`
aunque el paquete sí estaba en el venv. La causa real era que
`AsyncSocketModeHandler` requiere `aiohttp` como dependencia transitiva
y `slack-bolt` no la trae automáticamente.

**Diagnóstico**: el log mostraba `WARNING core.adapters.slack slack-bolt
not installed, slack adapter inactive`. Mensaje engañoso porque la
librería sí estaba — fallaba el `from slack_bolt.adapter.socket_mode...`
por `aiohttp` ausente, y el `except ImportError` capturaba todo bajo el
mismo mensaje.

**Fix**: `aiohttp>=3.10,<4.0` agregado a `core/requirements.txt` con
comentario explicando el motivo.

**TODO follow-up**: el `except ImportError` de `core/adapters/slack.py`
debería distinguir entre "slack-bolt missing" vs "alguna dependencia
async missing" y reportar el módulo real que falló.

### 2. Meta-prompt del Architect inyectaba restricciones temporales en bodies de agentes

**Síntoma**: el Architect generaba bodies con frases tipo *"Sin
integraciones directas a YouTube API por ahora; trabaja con lo que
puedas recuperar vía búsqueda web."* Una vez configurado el MCP de
YouTube, el agente seguía leyendo esa frase como verdad y NO usaba el
MCP — el modelo confía en su body.

**Fix**: bloque "CRITICAL — agent body must NOT mention integration
availability" agregado al meta-prompt en `core/architect/proposer.py`.
Las integraciones disponibles se determinan en runtime por
`mcp_servers`, no se hardcodean en el body. Si una integración falta,
el Architect debe mencionarla en `rationale` (visible al humano), no
en `body` (visible al modelo).

**TODO follow-up**: agentes ya deployados con bodies que tienen frases
hardcoded necesitan editarse a mano (o redeployarse). Considerar un
script `scripts/lint-agent-bodies.py` que detecte frases tipo "sin X
por ahora" y avise al usuario.

---

## Gaps de UX encontrados — sprints siguientes

### Sprint A — MCP Catalog (alta prioridad)

**Problema**: hoy el usuario debe saber el nombre exacto del paquete
npm (`@notionhq/notion-mcp-server`), el comando (`npx`), el formato de
los args (`-y @notionhq/notion-mcp-server`), las env keys exactas
(`NOTION_TOKEN`, `YOUTUBE_API_KEY`, etc.) y dónde generar cada
credencial. Esto es trabajo de developer, no de usuario final. OpenClaw
lo resuelve con un wizard de onboarding.

**Propuesta**: nueva sección en Settings → "MCP Catalog" con presets
predefinidos:

| MCP | Paquete | Credencial | Link a generar |
|---|---|---|---|
| Notion | `@notionhq/notion-mcp-server` | `NOTION_TOKEN` | https://www.notion.so/profile/integrations |
| Slack | adapter nativo | bot token + app token | https://api.slack.com/apps |
| Asana | MCP V2 cloud (HTTP/SSE) | OAuth 1-click | https://mcp.asana.com/v2/mcp |
| Gmail (read/send) | `@gongrzhe/server-gmail-autoauth-mcp` | OAuth flow local | Google Cloud Console |
| Google Calendar | `@cocal/google-calendar-mcp` | OAuth flow local | Google Cloud Console |
| YouTube (search) | **custom Python** (ver Sprint C) | API key | Google Cloud Console |
| GitHub | `@modelcontextprotocol/server-github` | personal access token | https://github.com/settings/tokens |
| Linear | `@modelcontextprotocol/server-linear` | API token | https://linear.app/settings/api |

Cada preset trae:
- Nombre + descripción humana
- Paquete (oculto, autocompletado)
- Lista de env vars que pide (con descripción de cada una)
- Link directo "Generar token aquí" al lugar exacto del proveedor
- Botón "Probar conexión" que valida antes de guardar (verde/rojo con
  motivo)

### Sprint B — UX Schedules (media prioridad)

**Problema**: el campo cron expression del schedule está en UTC sin
conversión visual. Un usuario chileno que quiere "06:00 todos los días"
debe saber que en UTC son `0 9 * * *` (UTC-3 estándar) o `0 10 * * *`
(UTC-4 horario de verano). Engorroso y propenso a error.

**Propuesta**:
- Agregar selector de timezone en el formulario de schedule.
- Mostrar al lado del cron expression: `0 9 * * * = 06:00 America/Santiago diario`
- Selector de timezone default = el del usuario (detectado desde
  `Intl.DateTimeFormat().resolvedOptions().timeZone`).
- Persistir el timezone en el schedule para mostrarlo y para
  recalcular si cambia el horario de verano.

### Sprint C — Skills custom pendientes (alta prioridad)

Algunas integraciones no tienen MCP server confiable en npm. Para esas,
escribir skills custom Python que vivan en `core/skills/builtin/`:

#### youtube-search (Python custom)
- El ecosistema de YouTube MCPs en npm está roto: `youtube-mcp-server`
  no exporta binario, `zubeid-youtube-mcp-server` falla por
  `@modelcontextprotocol/sdk` no resuelto en su dist CommonJS,
  `@a.ardeshir/youtube-mcp` requiere OAuth completo (no solo API key).
- Solución: ~50 líneas con `googleapiclient.discovery` que exponen
  `search_videos`, `get_video_details`, `get_channel_recent_videos`.
- Credencial: solo API key (no OAuth), muy simple.

#### gmail-read y gmail-send
- Usar `@gongrzhe/server-gmail-autoauth-mcp` (MCP server público
  maduro, probado).
- Wizard de OAuth: "click → autoriza con tu cuenta Google → vuelve".
- Diferenciar lectura (cuenta personal) de envío (cuenta de bot tipo
  `tu-bot@example.com`) en la UI del catalog.

#### calendar-read
- Usar `@cocal/google-calendar-mcp` (npm, multi-cuenta, free/busy
  queries).
- Mismo flujo OAuth que Gmail.

#### asana
- Asana V2 oficial (cloud-hosted): `https://mcp.asana.com/v2/mcp`.
- Transport HTTP/SSE, no stdio. Rugol soporta solo stdio hoy
  (línea 338 de `dashboard/src/app/agents/[id]/page.tsx`,
  `type: "stdio"` hardcoded).
- Para soportar Asana hay que extender el tipo en la UI y en el
  payload que se manda a `claude-agent-sdk`. El SDK ya soporta los 3
  transports (stdio/sse/http), solo falta exponer los otros dos en la
  UI.

### Sprint D — Edit en MCP servers (baja prioridad pero molesto)

**Problema**: la pestaña MCP del agente solo permite Add y Delete,
no Edit. Si te equivocaste en un valor, hay que eliminar y recrear,
re-pegando todo.

**Propuesta**: botón "Edit" al lado de cada MCP server listado.
Reusa el mismo formulario, prepoblado con valores actuales.

### Sprint E — Status visible en UI (alta prioridad)

**Problema**: cuando un adapter falla al iniciar (Slack en este caso),
la UI muestra `configured · not running` sin razón. El usuario tiene
que ir a logs en la terminal para descubrir el motivo.

**Propuesta**:
- Cuando `_restart_telegram` o `_restart_slack` capturan una
  excepción, persistir el mensaje (con stacktrace truncado) en
  `runtime_state` bajo `last_telegram_error` / `last_slack_error`.
- Mostrar ese mensaje en la sección correspondiente de Settings con
  ícono de warning y el texto del error real.
- Botón "Restart" al lado del estado para reintentar sin tener que
  re-pegar tokens.

### Sprint F — Pasada chilena (deuda histórica de copy)

**Problema**: muchos archivos del repo (READMEs, templates,
OnboardingHero, AgentChat, mensajes de adapters) tienen voseo
rioplatense ("vos sos", "tenés", "decile", "pegá", "fijate"). El
usuario principal del proyecto es chileno y se molesta cuando lo lee.

**Propuesta**: pasada dedicada con review humano. NO automática
(replace_all en strings es peligroso, ya rompió `Sos ` → `Eres`
generando `Ereselagente` en una pasada inicial).

Archivos identificados con voseo:

- `core/templates/catalog.py` (templates curados)
- `agents-templates/morning-brief.md`
- `agents-templates/inbox-triage.md`
- `agents-templates/evening-checkpoint.md`
- `README.es.md`
- `docs/install-on-new-pc.md`
- `dashboard/src/app/architect/page.tsx`
- `dashboard/src/app/agents/[id]/page.tsx`

Reemplazos seguros (con espacios):

| Voseo | Chileno |
|---|---|
| `Sos ` | `Eres ` |
| ` sos ` | ` eres ` |
| ` mirá ` | ` mira ` |
| ` Mirá ` | ` Mira ` |
| ` decí` | ` di` |
| ` Decí` | ` Di` |
| ` agregá` | ` agrega` |
| ` pegá` | ` pega` |
| ` buscá` | ` busca` |
| ` probá` | ` prueba` |
| ` andá` | ` ve` (chileno) |
| ` tenés` | ` tienes` |
| ` podés` | ` puedes` |
| ` querés` | ` quieres` |
| ` hacés` | ` haces` |
| ` sabés` | ` sabes` |
| `decile` | `dile` |
| `pedile` | `pídele` |
| `pasame` | `pásame` |
| `mandame` | `mándame` |
| `fijate` | `fíjate` |

### Sprint G-bis — Wizard conversacional de MCPs y agentes desde Telegram/Slack (alta prioridad)

**Pedido del usuario (2026-05-05)**: en OpenClaw el setup de MCPs y
agentes se puede hacer desde Telegram en formato conversacional. El
bot pide los tokens cuando los necesita, te explica de dónde sacarlos,
y guarda al final. Que Rugol soporte lo mismo.

**Propuesta — comandos del bot (Telegram + Slack):**

| Comando | Qué hace |
|---|---|
| `/setup_mcp` | Inicia wizard conversacional. Bot pregunta qué MCP quieres agregar (lista de presets), pide tokens uno por uno explicando dónde sacarlos, valida la conexión, y guarda. |
| `/setup_agent` | Wizard conversacional para crear un agente nuevo. Pregunta nombre, modelo, rol en una línea, qué MCPs usa, schedule opcional. |
| `/list_mcps` | Lista los MCPs configurados por agente. |
| `/test_mcp <agente> <mcp>` | Dispara una invocación de prueba al MCP y devuelve resultado. |
| `/help_prompt` | Atajo a la guía "buen prompt para proyecto" (ver Sprint G-tris). |

**Diseño**: cada wizard es una mini-state-machine en el adapter
(Telegram/Slack). Se persiste en `runtime_state` la sesión del wizard
por chat (qué paso vamos, qué respuestas llevamos). El usuario puede
cancelar con `/cancel` en cualquier momento.

**Importante**: los tokens NUNCA se guardan en el chat — se reciben,
se aplican al runtime_state, y el bot edita su propio mensaje de
confirmación reemplazando el token con `xxx...xxx`.

### Sprint G-tris — Guía interactiva de "buen prompt para proyecto" (alta prioridad)

**Pedido del usuario (2026-05-05)**: que el Architect incluya una guía
clara de cómo escribir un buen prompt para que el equipo generado sea
útil. Hoy un usuario nuevo no sabe qué nivel de detalle dar, qué meter
en idea vs constraints, qué restricciones funcionan vs cuáles
confunden al modelo.

**Propuesta — sección "Cómo armar un buen prompt" en `/architect`:**

Mostrar al lado del formulario de Architect (o en un toggle expandible)
los siguientes bloques:

1. **Idea (una línea)**:
   - Empezar con el outcome real, no la herramienta.
   - Ejemplo bueno: "Asistente personal coordinador para Edu (líder
     BI, divulgador IA): orquesta sub-agentes y ayuda a pensar mejor."
   - Ejemplo malo: "Quiero un asistente con muchas integraciones."

2. **Constraints — qué meter** (orden recomendado):
   - **USUARIO**: quién es, dónde vive, idioma preferido, qué le
     molesta (jergas, tono corporativo, etc).
   - **EQUIPO**: cuántos agentes, nombres, rol no superpuesto de cada
     uno, modelo sugerido por complejidad (haiku/sonnet/opus).
   - **LECCIONES INICIALES**: reglas que cada agente debe leer antes
     de actuar (idioma, voto explícito, no inventar datos, qué
     confirmar antes de actuar externamente).
   - **SCHEDULES SUGERIDOS**: cron + qué tarea, en zona horaria del
     usuario (el sistema convierte a UTC).
   - **RESTRICCIONES**: lo que NO debe proponer el Architect
     (integraciones que aún no existen como skills, multi-bot que
     todavía no soportamos, etc).

3. **Constraints — qué NO meter**:
   - Restricciones temporales tipo "sin Gmail por ahora" — eso
     contamina el body del agente cuando después conectes Gmail.
   - Listas larguísimas (>4000 chars el backend rechaza).
   - Detalles de implementación (paquetes npm, comandos, etc).

4. **Ejemplos descargables**: 3-4 prompts completos de proyectos
   tipo (asistente personal, marca personal, hija aprende jugando,
   pipeline comercial) que el usuario puede inspeccionar y modificar.

**Implementación**: archivo `docs/prompt-guide.md` + componente
`<PromptGuide />` en `dashboard/src/app/architect/page.tsx` que lo
renderiza con tabs (Idea / Constraints / Anti-patrones / Ejemplos).
Botón "Copiar este ejemplo" en cada uno.

### Sprint G-quater — Chat de configuración inteligente (paste-and-go)

**Pedido del usuario (2026-05-05)**: poder pegarle al sistema *"toma,
te comparto esto"* (un JSON de OpenClaw, un texto con credenciales, un
.env, un fragmento de docs) y que él entienda qué es, lo configure
solo en los lugares correctos, y pida solo lo que falte.

**Propuesta — vista "Asistente de configuración"** en el dashboard:

- Textarea grande donde el usuario pega lo que sea (JSON, texto, env,
  link).
- Un agente meta (modelo opus, system prompt especializado en
  config Rugol) lee el contenido y devuelve un plan estructurado:
  - "Detecté un Notion token y un Slack bot token."
  - "Voy a configurar Notion en gugol y chikilfumi (los agentes con
    rol de investigación). ¿Confirmas?"
  - "El Slack bot token lo pego en Settings → Slack."
  - "Falta el SLACK_APP_TOKEN para Socket Mode — ¿lo tienes?"
- Botón "Aplicar plan" que ejecuta los cambios via las APIs internas
  de Rugol (`update_settings`, `update_agent_mcp_servers`, etc).
- Tokens nunca se persisten en el chat ni en logs; solo se aplican a
  runtime_state.

**Trampa**: el meta-agente que parsea necesita prompt MUY estricto
para evitar alucinar configuraciones (ej: "creo que esto es un token
de Asana" cuando es algo distinto). Mejor: que diga explícitamente
"no estoy seguro qué es esto, ¿me confirmas que es X?" antes de
aplicar.

**Esta feature es la diferencia entre "herramienta para devs" y
"copilot de configuración"** — exactamente el gap que Edu identifica
respecto a OpenClaw.

### Sprint G-quinque — Config a nivel proyecto, no solo agente (alta prioridad)

**Pedido del usuario (2026-05-05)**: hoy el setup obliga a configurar
cada MCP en cada agente que lo necesita. Si un MCP de Notion sirve
para 3 agentes (gugol + chikilfumi + delichul), hay que pegar la
config 3 veces.

**Propuesta — MCPs heredables del proyecto:**

- Cada proyecto tiene su propia sección de MCPs en su página
  (`/projects/<slug>` → tab "MCPs del proyecto").
- Los MCPs configurados a nivel proyecto se heredan automáticamente
  por todos los agentes del equipo, salvo que el agente los desactive
  explícitamente (toggle "Desactivar para este agente").
- En la pestaña MCP del agente individual, mostrar dos secciones:
  **Heredados del proyecto** (read-only, con toggle de desactivar) y
  **Solo para este agente** (CRUD normal).

**Beneficio**: configurar Notion una sola vez en `Gugolproject` lo
deja disponible para los 4 agentes del equipo automáticamente.
Reduce setup de N×M a N+M.

**Migración**: los MCPs ya configurados a nivel agente quedan como
"agente-only" (no rompe nada). El usuario puede promoverlos a "proyecto"
con un click ("Mover a config del proyecto") si los reutiliza.

### Sprint G — Delegación real entre agentes (alta prioridad)

**Problema**: cuando el usuario le dice a gugol "delegale a delichul que
busque videos", gugol responde "en nombre de" delichul usando sus
propias herramientas, no spawnea un subprocess real de delichul.
Resultado: el MCP que está conectado a delichul (YouTube en este caso)
no se invoca.

**Propuesta**: extender el orchestrator para soportar `delegate_to`
como tool exponible al agente coordinador. Cuando gugol llama a
`delegate_to(agent_name="delichul", prompt="...")`, el orchestrator
encola un run real de delichul con su propio config (model + body +
mcp_servers + lessons del proyecto), espera el final_text, y devuelve
ese texto a gugol como observation. Gugol consolida y responde.

Esto desbloquea el modelo Gugol completo de OpenClaw donde la
coordinadora orquesta sub-agentes especialistas.

---

## Skills custom pendientes — orden recomendado

| # | Skill | Esfuerzo | Bloquea |
|---|---|---|---|
| 1 | Asana MCP V2 (cloud) | extender Rugol para soportar HTTP/SSE transport | brief diario de gugol con pendientes BI reales |
| 2 | Gmail-read | OAuth flow + MCP gongrzhe | gugol vea inbox personal |
| 3 | Gmail-send | OAuth flow + MCP gongrzhe (cuenta bot dedicada) | gugol responda emails con confirmación |
| 4 | Calendar-read | OAuth flow + MCP cocal | brief diario con agenda real |
| 5 | YouTube-search custom Python | escribir skill (50 líneas) | delichul recomiende videos reales con duración/fecha |

---

## Deuda chica (paper cuts)

- El bot de Slack imprime `Este canal (X) no está vinculado todavía.
  Prueba @bot bind <agente> o usa el dashboard.` — verificar que el
  comando `bind` realmente funcione vía mention. En la sesión de hoy
  el adapter aceptó `bind gugol` por DM pero el flujo en canal con
  `@Rugol bind gugol` quedó silencioso (probablemente porque event
  subscriptions no incluían lo necesario hasta el reinstall).
- El instalador `installer/wizard.ps1` agrega tokens al `.env` directo.
  Cuando Settings UI tenga Status visible (Sprint E), el wizard
  debería redirigir al dashboard en vez de escribir el `.env` —
  evita inconsistencia entre dos fuentes de verdad.
