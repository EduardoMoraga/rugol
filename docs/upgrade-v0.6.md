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

Asume que ya tienes Rogologo corriendo y conectado al repo en
`C:\Moragent\rogologo`. Si arrancas desde cero, primero seguí
[`docs/install-on-new-pc.md`](install-on-new-pc.md).

### Paso 1 — Apaga ambos servidores

- Terminal del backend (uvicorn) → **Ctrl + C**
- Terminal del frontend (pnpm dev) → **Ctrl + C** (escribí `Y` si pregunta confirmación)

No cierres las ventanas; las vamos a reusar.

### Paso 2 — Trae el código nuevo

En la terminal del backend:

```powershell
cd C:\Moragent\rogologo
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
cd C:\Moragent\rogologo\dashboard
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

En el chat con tu bot Rogologo (Telegram):

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

- 4 bot tokens de Telegram (gugol, rogologo, delichul, chikilfumi)
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
extra de Telegram (porque Rogologo soporta UN bot por instancia, los otros
quedan documentados como 'no aplicado').

Marcá las acciones que querés, dale Aplicar. Reiniciá el backend.

---

## Comandos rápidos para encender/apagar (post-upgrade)

```powershell
# Backend
cd C:\Moragent\rogologo
.\.venv\Scripts\python.exe -m uvicorn core.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (otra terminal)
cd C:\Moragent\rogologo\dashboard
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

5. **Paso manual una sola vez** (esto Rogologo no lo puede hacer porque
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
   - Comando: ruta absoluta del Python del venv (ej: `C:\Moragent\rogologo\.venv\Scripts\python.exe`)
   - Args: ruta absoluta al script (ej: `C:\Moragent\rogologo\scripts\mcp\youtube_server.py`)
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
