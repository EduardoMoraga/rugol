# Upgrade a v0.6 — Guía paso a paso

> Cambios principales de esta versión: experiencia de uso para configurar
> integraciones. Cinco features nuevas resuelven el "configuré algo, no
> sé si funciona, no puedo editarlo" que dolió en la sesión 2026-05-05.

## Lo nuevo

| # | Feature | Dónde se usa |
|---|---------|--------------|
| 1 | **Test Connection per-MCP** | `/agents/<id>` → tab MCP → botón **Probar** en cada server |
| 2 | **Edit MCP servers** | Mismo lugar → botón **Editar** (antes había que borrar y recrear) |
| 3 | **Guía de buen prompt** | `/architect` → expandir *"Cómo armar un buen prompt"* (4 ejemplos copiables) |
| 4 | **Wizard conversacional Telegram** | Comandos `/setup_mcp`, `/list_mcps`, `/test_mcp`, `/cancel`, `/help_prompt` |
| 5 | **Asistente de configuración (paste-and-go)** | Nueva ruta `/config-assistant` en el nav |

Más bug fix interno: el adapter Slack ahora reporta el módulo Python real
que falta cuando no logra importarse, en vez del genérico
`slack-bolt not installed`.

---

## Aplicar el upgrade en tu PC

Asume que ya tienes Rugol corriendo y conectado al repo en
`C:\Moragent\rugol`. Si arrancas desde cero, primero seguí
[`docs/install-on-new-pc.md`](install-on-new-pc.md).

### Paso 1 — Apaga ambos servidores

- Terminal del backend (uvicorn) → **Ctrl + C**
- Terminal del frontend (pnpm dev) → **Ctrl + C** (escribí `Y` si pregunta confirmación)

No cierres las ventanas; las vamos a reusar.

### Paso 2 — Trae el código nuevo

En la terminal del backend:

```powershell
cd C:\Moragent\rugol
git pull
```

Vas a ver ~10-15 archivos modificados.

### Paso 3 — Instala dependencias actualizadas

```powershell
.\.venv\Scripts\python.exe -m pip install -r core/requirements.txt
```

### Paso 4 — Levanta el backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn core.main:app --host 127.0.0.1 --port 8000 --reload
```

Mirá los logs de arranque. Tienen que aparecer:

```
INFO core.adapters.telegram telegram adapter started ...
INFO core.adapters.slack slack adapter started (socket mode)
INFO:     Application startup complete.
```

### Paso 5 — Levanta el frontend

En la otra terminal:

```powershell
cd C:\Moragent\rugol\dashboard
pnpm install
pnpm dev
```

(El `pnpm install` corre rápido — solo instala lo nuevo si lo hubiera.)

### Paso 6 — Verifica el upgrade

Abrí `http://localhost:3000` y validá uno por uno:

#### A) Test Connection en MCP (Sprint 1)

1. `/agents` → click en **gugol** → tab **MCP**.
2. Sobre el server `notion` (que ya tenés configurado), click en **Probar**.
3. Esperá 1-3 segundos. Tiene que aparecer un badge:
   - **Verde** "OK · N herramientas · X ms" → el MCP está bien.
   - **Rojo** "Falló · timeout/spawn_failed/etc" → el MCP no responde, ahora sabés exactamente por qué.

#### B) Edit en MCP (Sprint 2)

1. Sobre el mismo server `notion`, click en **Editar**.
2. El form de abajo se prepuebla con la config actual (nombre, comando, args, env masked).
3. Cambiá algo (ej: agregá un arg) y click en **Aplicar cambios al borrador**.
4. Arriba aparece el server actualizado. Click en **Guardar** (botón superior derecho).
5. Verificá con **Probar** que sigue funcionando.

#### C) Guía de buen prompt (Sprint 3)

1. `/architect`.
2. Arriba del formulario hay una card colapsable: **"Cómo armar un buen prompt"**.
3. Click → se abre con 4 tabs: Idea, Constraints, Anti-patrones, Ejemplos.
4. En **Ejemplos**, click en **Copiar** sobre cualquier plantilla.
5. Los campos del Architect se autocompletan. Editá lo que quieras y dale Proponer.

#### D) Wizard Telegram (Sprint 4)

En el chat con tu bot Rugol (Telegram):

```
/setup_mcp
```

El bot te lleva paso a paso:

1. *"¿A qué agente?"* → escribí `gugol`
2. *"¿Qué MCP?"* → escribí `notion` (o `asana`, `github`, `brave-search`, `filesystem`)
3. *"Pegame el token"* → te explica de dónde sacarlo, pegás.
4. El bot guarda la config y corre el test automáticamente. Te dice si OK con N tools, o el error específico.

Otros comandos:

- `/list_mcps` — muestra qué MCPs tiene cada agente.
- `/test_mcp gugol notion` — corre el handshake JSON-RPC contra ese MCP, devuelve OK/error.
- `/cancel` — sale de cualquier wizard a medias.
- `/help_prompt` — pista resumida sobre cómo armar prompts para el Architect.

#### E) Asistente de configuración paste-and-go (Sprint 5)

1. En el nav rail, vas a ver una nueva entrada: **"Asistente config"** (icono varita).
2. Click → se abre `/config-assistant`.
3. En el textarea pegá lo que quieras parsear:
   - El JSON de OpenClaw (`C:\Moragent\04-LAB\openclaw-pc-exclusivo\openclaw.fixed.json`)
   - Un `.env`
   - Texto libre con tokens
   - Una nota privada con credenciales
4. Click **Analizar**.
5. Esperá 30-60 segundos. El asistente lee el contenido con Claude y devuelve un plan de acciones (set Telegram token, set Slack tokens, agregar MCP X al agente Y, etc).
6. Cada acción tiene un checkbox. Marcá las que querés aplicar.
7. Click **Aplicar (N)**. El backend usa la versión cacheada del plan (los tokens nunca volvieron al frontend en claro).
8. El resultado muestra OK/error por acción. Si configuraste tokens de Telegram o Slack, **reiniciá el backend manualmente** (Ctrl+C en uvicorn + relanzar) para que los adapters recarguen.

> Privacidad: los valores con apariencia de secret (token, key, password)
> se enmascaran (`abcd…wxyz`) en el plan que ve el frontend. La versión
> con valores reales vive 10 minutos en memoria del backend y se borra
> después de aplicar.

---

## Probá el caso real: tu JSON de OpenClaw

El JSON `openclaw.fixed.json` que ya tenés contiene:

- 4 bot tokens de Telegram (gugol, rugol, delichul, chikilfumi)
- 1 bot token + app token de Slack
- Notion token
- API keys de Anthropic, OpenRouter, Google AI Studio

Pegalo entero en el Asistente de configuración y dale Analizar. Vas a ver
algo así:

```
[set_telegram_token] Configurar bot Telegram principal con el token de "gugol"
[set_slack_tokens]   Configurar Slack adapter con bot token + app token del workspace
[add_mcp]            Agregar Notion MCP a gugol con el NOTION_TOKEN provisto
[add_mcp]            Agregar Notion MCP a chikilfumi con el NOTION_TOKEN provisto
```

Más una sección "El asistente vio cosas que no clasificó" con los 3 bots
extra de Telegram (porque Rugol soporta UN bot por instancia, los otros
quedan documentados como 'no aplicado').

Marcá las acciones que querés, dale Aplicar. Reiniciá el backend.

---

## Comandos rápidos para encender/apagar (post-upgrade)

```powershell
# Backend
cd C:\Moragent\rugol
.\.venv\Scripts\python.exe -m uvicorn core.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (otra terminal)
cd C:\Moragent\rugol\dashboard
pnpm dev
```

---

## Si algo no anduvo

| Síntoma | Mira |
|---|---|
| El nav rail no muestra "Asistente config" | Hard refresh del browser (Ctrl+Shift+R). El componente cliente se cachea. |
| `/config-assistant/parse` da timeout | Tu input es muy largo. El backend lo trunca a 12000 chars; igual probá con menos. |
| El wizard de Telegram no responde | Verificá `/cancel` (limpia state). Después `/setup_mcp` arranca de cero. |
| El botón Probar dice "spawn_failed" | El comando que configuraste no se encuentra (típico: `npx` no en PATH del usuario que corre uvicorn). |
| El botón Probar dice "not_installed" | El paquete npm no está publicado o no exporta binario ejecutable. Probá otro preset. |
| Slack sigue diciendo "configured · not running" | Mirá los logs del backend — ahora dicen el módulo Python específico que falta (`aiohttp`, `websockets`, etc). |

---

## Anti-alucinación + sandbox de filesystem (fix urgente)

**Bug detectado (2026-05-06):** un agente respondió a *"está todo OK con
los schedules?"* con una tabla ficticia que mezclaba "Lucy Morning
Briefing", "SKF Daily Reports" y otros nombres de proyectos previos del
usuario. La tabla era plausible pero inventada — el agente no tenía un
tool real para listar APScheduler, así que leyó un script en
`C:\Moragent\00-CORE\tools\moragent.py` (un proyecto distinto) y se lo
entregó al usuario como verdad.

Causa raíz: combinación de tres factores:
1. `permission_mode="bypassPermissions"` + Read tool = el agente puede
   leer cualquier archivo de la máquina, incluso fuera del workspace.
2. NO existe tool que liste el estado real de Rugol (schedules,
   runs, agents) — solo la base de SQLite, que el agente no consulta
   directamente.
3. Sin instrucciones explícitas anti-alucinación, el modelo confía en
   archivos plausibles del filesystem como si fueran la fuente.

**Fix aplicado en `core/runner/claude_runner.py`:**

El system prompt que recibe cada agente ahora incluye dos secciones nuevas:

- **CRITICAL — anti-hallucination rule**: enseña explícitamente que el
  estado runtime de Rugol NO está en archivos. Le pasa al agente
  los endpoints REST exactos (`GET /api/schedules`, `GET /api/agents`,
  `GET /api/runs`, etc.) que puede consultar con `curl` cuando el
  usuario le pregunte por ese estado. Si la API no responde, debe
  decirlo explícitamente, no caer al filesystem como fallback.

- **Filesystem sandbox**: instrucción dura de NO leer fuera del
  workspace. Si el agente necesita algo de afuera, debe pedir
  autorización al usuario primero.

Estos son **defense-in-depth via prompt** — no son seguridad técnica
absoluta (un modelo puede ignorar instrucciones), pero corrigen el
80% de los casos. Para sandbox físico (chroot, contenedor) la
defensa es más fuerte pero implica más complejidad y queda en
roadmap si se vuelve necesario.

---

## Memoria de largo plazo (Sprints A + B)

Dos cambios encadenados que cierran el gap de "el agente olvida todo
entre sesiones".

### Sprint A — `session_id` persistido en SQLite

Antes: el adapter de Telegram/Slack guardaba el `session_id` (que
claude-agent-sdk usa para continuar una conversación) en un dict en
RAM. Reiniciar `uvicorn` borraba el dict, así que tras un restart el
agente decía *"no tengo contexto de la conversación anterior"*.

Ahora: hay una tabla `chat_sessions (channel_type, external_id,
session_id, last_used_at)`. Cuando un run completa, el adapter persiste
el session_id ahí. Cuando uvicorn arranca, los adapters cargan la tabla
en su cache RAM. La conversación con gugol del jueves sigue activa el
viernes después de un restart.

Para borrar a propósito: `/reset` (Telegram) o `reset` (Slack) borra
ambas memorias — RAM y DB.

### Sprint B — Auto-memoria file-based per agente

Inspirado en cómo funciona la auto-memoria de Claude Code en tu PC.

Nuevo directorio (creado al primer uso, ignorado por git):

```
agent-memory/
  gugol/
    MEMORY.md                    # índice
    20260506-edu-prefiere-...md  # una memoria
    20260506-decision-sobre-...md
  delichul/
    ...
```

Cada memoria es un archivo `.md` con frontmatter (`name`, `description`,
`kind`, `created_at`) más el body. El orchestrator antes de cada run
arma un bloque "## Tu memoria persistente" con todas las memorias del
agente (greedy hasta 4000 chars) y lo agrega al system_prompt junto
con la misión del proyecto y las lecciones.

**Cómo agregar memorias:**

1. **Telegram (más rápido):**
   ```
   /remember edu prefiere videos en español de más de 30 minutos
   ```
   El comando agarra todo lo que viene después y lo guarda en la memoria
   del agente bound al chat. El primer chunk del texto se usa como
   título.

2. **Telegram — listar:**
   ```
   /memories
   ```
   Muestra los nombres de todas las memorias del agente bound.

3. **API:**
   ```
   POST /api/agents/{id}/memories
   { "name": "...", "description": "...", "body": "...", "kind": "note" }

   GET    /api/agents/{id}/memories
   DELETE /api/agents/{id}/memories/{file_or_name}
   ```

4. **Manual:** crear el archivo `.md` directo en `agent-memory/<name>/`
   con el frontmatter — el orchestrator lo lee la próxima corrida.

**El agente puede escribir sus propias memorias.** Como tiene Write
tool de Claude Code activo, puede crear archivos en
`agent-memory/<su-name>/`. Si le decís "guardá esto en tu memoria", lo
hace solo (le tendrías que indicar la ruta una vez, o agregárselo al
body del agente como instrucción permanente).

**Privacidad:** `agent-memory/` está en `.gitignore` — las memorias
no se commitean. Son locales a tu PC.

---

## Web scraping con Playwright

`@playwright/mcp` (MCP oficial de Microsoft) está disponible como preset
en el catálogo. El agente puede navegar URLs, extraer contenido,
rellenar formularios, hacer clicks y tomar screenshots usando
accessibility trees (más robusto que CSS selectors).

### Setup (una sola vez)

Instalar Chromium en tu PC:

```powershell
npx playwright install chromium
```

(~250 MB. Es la única dependencia externa que Playwright necesita.)

### Activar en un agente

Tres caminos como cualquier otro MCP:

**A) Dashboard:**
- `/agents/<id>` → MCP → Agregar
- Nombre: `playwright`
- Comando: `npx`
- Args: `-y @playwright/mcp@latest`
- Env: vacío
- Save → Probar.

**B) Telegram (más fácil):**
```
/setup_mcp
```
Agente → preset `playwright` → listo (no pide tokens, no pide nada).

**C) Paste-and-go: pegale al config-assistant cualquier referencia a
"quiero scraping" o un link a un sitio que querés monitorear, y va a
proponer `add_mcp` con `preset_id=playwright`.

### Probar

Después de bindear el chat al agente con Playwright:

```
Edu: andá a https://news.ycombinator.com y contame cuáles son los 5 títulos top
agente: [navega, extrae, responde con los títulos]
```

### Tools que expone

`browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`
(accessibility tree de la página actual), `browser_screenshot`,
`browser_wait_for`, entre otros. El agente decide cuáles usar según la
tarea.

---

## Multimodal en Telegram — fotos, PDFs, Office docs y audio

Detectado al usar el bot de gugol: solo aceptaba texto. Cualquier foto,
PDF, Word o audio que el usuario mandaba se ignoraba silenciosamente.
v0.6 lo arregla: el adapter Telegram ahora acepta los 4 tipos.

### Qué se puede mandar al bot

| Tipo | Cómo se procesa | Soportado de fábrica |
|---|---|---|
| **Imagen** (PNG, JPG, WebP, etc.) | Se baja a `data/uploads/<chat_id>/`. El prompt al agente incluye el path absoluto. Claude la lee con su tool Read (vision nativo). | ✅ Sin instalación extra |
| **PDF** | Igual. Claude PDFs nativos. | ✅ Sin instalación extra |
| **Word (.docx)** | Se baja, se extrae texto con `python-docx`, se inyecta inline en el prompt (truncado a 18000 chars). | ✅ Con `pip install` actualizado |
| **Excel (.xlsx, .xlsm)** | Igual con `openpyxl`. Cada hoja como sección, filas pipe-separadas. | ✅ Con `pip install` actualizado |
| **PowerPoint (.pptx)** | Igual con `python-pptx`. Texto por slide. | ✅ Con `pip install` actualizado |
| **Texto plano** (.txt, .md, .csv, .json, .yaml, .py, .js, .ts) | Lectura UTF-8 directo. | ✅ Sin instalación extra |
| **Audio / nota de voz** | Se baja, se transcribe con **faster-whisper local** (CPU, int8, ~3-5s por minuto), se pasa el texto al agente. | ✅ Con `pip install` actualizado. Primera vez descarga modelo `small` (244 MB) |

### Primera vez con audio

La primera nota de voz que mandes va a tardar 30-60 segundos extra mientras
faster-whisper descarga el modelo `small` desde Hugging Face. El bot te
avisa con un mensaje *"Transcribiendo audio... (la primera vez puede tardar)"*.
La segunda vez, el modelo ya está en disco y la transcripción tarda lo
normal (~5 segundos para una nota de 30s).

Para usar otro modelo (más rápido o más preciso):

```powershell
$env:RUGOL_WHISPER_MODEL = "tiny"     # más rápido, menos preciso (~75 MB)
$env:RUGOL_WHISPER_MODEL = "medium"   # más preciso, más lento (~1.5 GB)
```

(Configurar **antes** de levantar uvicorn.)

### Cómo el agente "ve" lo que mandaste

- **Imagen y PDF**: el prompt le dice *"el usuario te envió un archivo, path: …"*
  y el agente usa Read para abrirlo. Para que esto funcione, el agente debe
  tener Read habilitado (es default en Claude Code).
- **Office docs / texto plano**: el contenido extraído va inline en el prompt.
  No necesita usar Read, ya tiene el texto delante.
- **Audio**: la transcripción se enseña primero al usuario (editando el
  mensaje "transcribiendo…") y después se pasa al agente como texto.

### Probar rápido

1. Mandale una foto a tu bot con caption *"qué se ve acá"* — el agente debería describirla.
2. Mandale un PDF — debería resumirlo o responderte sobre su contenido.
3. Mandale un .xlsx — debería resumir la planilla, filas relevantes, etc.
4. Mandale una nota de voz de 10 segundos diciendo cualquier cosa — el bot edita el mensaje con la transcripción y después responde.

### Dónde se guardan los archivos

`data/uploads/<chat_id>/<timestamp>-<filename>`

Esa carpeta NO se borra automáticamente. Si querés barrerla:

```powershell
Remove-Item -Recurse -Force C:\Moragent\rugol\data\uploads
```

Los archivos están en `.gitignore` (toda `data/` lo está).

---

## Memoria de conversación en Telegram y Slack (fix tardío)

Detectado al probar v0.6 con Gugol vía Telegram: cada mensaje arrancaba un
subprocess fresco sin contexto del turno anterior. Resultado: gugol decía
*"no tengo contexto de la conversación anterior"* a cada rato.

**Fix**: el adapter Telegram (y Slack) ahora persisten el `session_id` del
último run completado por chat/canal y lo reutilizan en el siguiente
mensaje. claude-agent-sdk usa eso para continuar la sesión.

**Cómo se usa**: nada que hacer — funciona automático. La memoria se
guarda en RAM del backend (se pierde si reinicias uvicorn, lo cual
funciona como reset implícito). Si querés borrarla a propósito sin
reiniciar:

- Telegram: comando `/reset` en el chat con tu bot.
- Slack: `@<bot> reset` (mismo handler).

---

## Caso real: configurar Google (Gmail / Calendar / Sheets / Drive)

> Detectado en la sesión 2026-05-05: el primer cut del Asistente de
> configuración no entendía Google OAuth — devolvía "0 acciones, vi
> credenciales pero no tengo preset". Se arregló en este mismo commit.

Google OAuth requiere un flujo distinto a Notion/Slack/Asana: necesitas
**credentials.json** (cliente OAuth) **+ token.json** (refresh token tras
autorizar). Los MCP servers de Google (`@gongrzhe/server-gmail-autoauth-mcp`,
`@cocal/google-calendar-mcp`) buscan el credentials en
`~/.gmail-mcp/gcp-oauth.keys.json` y manejan el flujo de auth ellos mismos.

### Pasos

1. **En el dashboard, andá a `/config-assistant`**.
2. **Pegá el JSON entero de credentials.json** (típicamente lo descargás
   desde Google Cloud Console → APIs & Services → Credentials → OAuth
   client ID, *Desktop app*). Ejemplo:
   ```json
   {"installed":{"client_id":"...apps.googleusercontent.com","client_secret":"GOCSPX-...","redirect_uris":["http://localhost"], ...}}
   ```
   Si tenés también una API Key tipo `AIzaSy...` (para YouTube por ej.),
   pegala en el mismo input — el assistant detecta ambas.

3. Click **Analizar**. El plan que devuelve incluye:
   - `setup_google_oauth_credentials` — escribe el credentials.json en
     `~/.gmail-mcp/gcp-oauth.keys.json` (o donde le digas).
   - `set_google_api_key` — guarda la API key en
     `data/secrets/google-api-key.txt` (queda lista para el MCP custom de
     YouTube cuando exista).
   - Eventualmente, `add_mcp` con preset `gmail` o `google-calendar` para
     algún agente — solo si el assistant interpreta que querés conectarlo.

4. Marcá las que querés y **Aplicar**.

5. **Paso manual una sola vez** (esto Rugol no lo puede hacer porque
   necesita un browser interactivo):
   ```powershell
   npx -y @gongrzhe/server-gmail-autoauth-mcp auth
   ```
   Te abre el browser, autorizás el scope, vuelve y guarda
   `~/.gmail-mcp/credentials.json`. A partir de ahí el MCP server queda
   listo para arrancar via npx en cada invocación.

6. Después podés agregar el MCP `gmail` a cualquier agente desde
   `/agents/<id>` → MCP → Agregar (preset `gmail`, sin env vars), o usar
   el wizard de Telegram `/setup_mcp` y elegir `gmail`.

### Lo que está soportado (y lo que no)

| Servicio | Estado | Cómo |
|---|---|---|
| **Gmail (read+send)** | ✅ con OAuth manual | `@gongrzhe/server-gmail-autoauth-mcp`. Una corrida única de `npx ... auth` para autorizar |
| **Google Calendar** | ✅ con OAuth manual | `@cocal/google-calendar-mcp`. Misma autorización OAuth que Gmail |
| **YouTube Data API** | ✅ sin OAuth (solo API key) | Custom MCP Python que vive en `scripts/mcp/youtube_server.py`. Lee la key de `data/secrets/google-api-key.txt` o de `YOUTUBE_API_KEY` en env. Tools expuestos: `search_videos`, `get_channel_recent`, `get_video_details` |
| Google Drive | ⏳ roadmap | El MCP oficial de Anthropic requiere Service Account, no OAuth Desktop. Distinto flow. Sprint dedicado. |
| Google Sheets | ⏳ roadmap | Idem Drive. |

### Cómo activar YouTube en delichul (o el agente que quieras)

**Si ya pegaste la API key vía `/config-assistant`** y el assistant generó
`set_google_api_key`, la key ya está en `data/secrets/google-api-key.txt`.
Solo falta agregar el MCP al agente:

**Opción A — desde el dashboard:**

1. `/agents/<id>` → MCP → Agregar:
   - Nombre: `youtube`
   - Comando: ruta absoluta del Python del venv (ej: `C:\Moragent\rugol\.venv\Scripts\python.exe`)
   - Args: ruta absoluta al script (ej: `C:\Moragent\rugol\scripts\mcp\youtube_server.py`)
   - Env: vacío (el script lee la key del archivo automáticamente)
2. Save → click **Probar** → debería devolver verde con tools `search_videos`, `get_channel_recent`, `get_video_details`.

**Opción B — más fácil, desde Telegram:**

```
/setup_mcp
```

Elegí el agente, después escribí `youtube` como preset. El wizard arma
automáticamente el comando con el Python del venv y la ruta absoluta al
script. Si tu API key ya está guardada, el test debería pasar de una.

**Opción C — paste-and-go:**

`/config-assistant` → pegá tu API key. El assistant ahora detecta que hay
un agente apto (delichul si tienes el setup tipo Gugol) y genera `add_mcp`
con preset `youtube` para ese agente, además del `set_google_api_key`.

---

## Lo que queda pendiente (roadmap-v0.6.md)

Esta versión cierra los gaps críticos de UX. Lo que sigue:

- Soporte para MCPs SSE/HTTP (Asana V2 oficial, Linear, etc) — hoy solo stdio.
- `/setup_agent` conversacional (paralelo a `/setup_mcp` pero para crear agentes).
- MCPs heredables del proyecto (configurás Notion una vez en el proyecto, los 4 agentes lo usan).
- Selector visual de timezone en schedules.
- Pasada chilena exhaustiva en bodies de agentes ya deployados (el commit anterior cubrió `core/templates/catalog.py` + READMEs + UI principal; los .md sueltos en `agents-templates/` quedaron untracked).

Detalle completo: [`docs/roadmap-v0.6.md`](roadmap-v0.6.md).
