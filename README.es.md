<div align="center">

# Rugol

**Tu orquestador de agentes IA — apoyo para las decisiones que importan.**

Una sala de control local donde tus equipos de agentes Claude hacen el
trabajo, desafían tu pensamiento y recuerdan lo que aprendiste — para que
decidas con un mejor proceso, no solo con más información.

[Quickstart](#quickstart) · [Por qué Rugol](#por-qué-rugol) · [Casos reales](#casos-reales) · [Cómo funciona](#cómo-funciona) · [English](README.md)

</div>

---

> **Las buenas decisiones no son cuestión de más información, sino de un mejor proceso.**

Rugol cambia el paradigma. No pensás "qué agente creo". Pensás
**qué querés resolver**: tu asistente personal, tu marca, ayudar a
tus proyectos, tu operación, tu pipeline de ventas. Cada uno
se arma con su propio equipo de agentes especialistas, una misión
escrita y reglas vivas. Los agentes hacen el trabajo y desafían tu
pensamiento — vos te quedás con la decisión, mejor informada y con
menos ruido.

---

## Por qué Rugol

### Hecho por alguien de negocio, no por un dev

Soy economista. Lidero proyectos de Business Intelligence en LATAM.
Vi cómo "agentic AI" estaba quedando atrapado en un lenguaje técnico
que excluye a las personas comunes — las mismas personas para las
que la herramienta puede cambiar la vida.

Rugol nace de esa frustración. Detrás del código (que armé con
Claude Code, claro), las decisiones de producto vienen de otro lado:
**economía conductual, problemas reales de productividad, vida
cotidiana**.

### El paradigma project-first

| Otras plataformas | Rugol |
|---|---|
| Lista plana de agentes sueltos | Proyectos como departamentos con misión |
| Tú decidís qué modelo usar (haiku/sonnet/opus) | Tú elegís el **tipo de tarea** (heurística / pensar / deliberar); el sistema rutea |
| Agente que actúa solo | Opcional: abogado del diablo cuestiona antes de actuar |
| Memoria por agente o ninguna | Lecciones vivas por proyecto que el equipo lee antes de cada tarea |
| Templates técnicos | Templates por resultado: "asistente personal", "gestión de proyectos", "analista de operaciones" |

### Tres principios de economía conductual encarnados en software

| Principio | Cómo aparece en Rugol |
|---|---|
| **Sistema 1 vs Sistema 2** (Kahneman) | El usuario no piensa en modelos. Elige *Heurística* (haiku, rápido), *Pensar* (modelo del agente) o *Deliberar* (opus, decisiones caras de revertir). |
| **Ruido** (Kahneman/Sunstein) | Antes de decisiones importantes, el "Abogado del diablo" (opus) cuestiona la respuesta primaria. Dos perspectivas, tú decidís. |
| **Sesgos** | Cada proyecto mantiene una lista viva de *lecciones* (lessons / biases / facts). Cada agente del equipo las lee antes de cada run. Lo que aprendiste de la mala queda como anclaje permanente. |

---

## Casos reales

### "Asistente personal"

Brief en la mañana, triage de inbox, captura al cierre del día. Tres
agentes para que llegues a la noche habiendo ejecutado tus prioridades y
no las de tu inbox.

### "Gestión de proyectos"

Para quien lleva varios proyectos y descubre los problemas tarde: un
agente compara el avance real contra el plan, otro persigue los bloqueos
hasta que tienen dueño y fecha, otro escribe el status semanal para quien
decide. Nada se cae en silencio.

### "Analista de operaciones"

Tres agentes en cadena estricta. El primero audita el dato crudo —huecos,
duplicados, saltos imposibles— y puede detener la cadena con un veredicto
de *no usar*. El segundo explica qué se movió y separa lo estacional de lo
estructural. El tercero cierra con una decisión costeada, incluyendo el
precio de no hacer nada. Ninguna correlación se presenta como causa.

### "Mi marca personal"

Tres agentes que cuidan la voz pública: brand-architect (Opus, decide qué
es On-brand), content-editor (escribe los posts), market-analyst (mide qué
resuena). Lecciones vivas como *"nunca usar 'leverage'"* o *"cero hype"*
quedan inyectadas en cada run, así el equipo no se desvía aunque tú no
estés mirando.

### "Pipeline comercial"

Para freelancers y founders que llevan ventas en una hoja de cálculo:
prospector + qualifier + follower-upper. Schedule diario que no deja
caer ningún follow-up activo. Honestidad sobre fit: si no somos para el
cliente, lo dice.

### "Investigador de un tema"

Cuando tienes que dominar algo nuevo en una semana: researcher recopila
fuentes, explainer las traduce a analogías cotidianas, critic cuestiona
el consenso. Te lleva de 0 a poder sostener una conversación informada.

---

## Cómo funciona

Tres conceptos. Eso es todo.

### 1. Proyecto = departamento con misión

Cada proyecto tiene nombre, color, ícono, una misión escrita (el porqué)
y un equipo de 1-5 agentes. La misión la lee cada agente del equipo
**antes de cada tarea** — funciona como anclaje contra la deriva.

### 2. Lecciones vivas

Cuando el equipo aprende algo (un sesgo detectado, una decisión, una
regla de negocio), lo agregás como lección al proyecto. La próxima vez
que cualquier agente del equipo trabaje, va a leerla. La memoria del
proyecto crece sin que nadie pierda contexto.

Cada respuesta del agente y cada crítica del abogado del diablo tiene
un botón **"Promover a lección"** — un click y ese aprendizaje queda
como anclaje permanente.

### 3. Tipo de tarea + abogado del diablo

Antes de cada mensaje al chat:

- **Heurística** → ruteo a haiku, respuesta rápida y barata.
- **Pensar** → modelo del agente, el default.
- **Deliberar** → ruteo a opus, razonamiento profundo.

Y un checkbox **"Pedir abogado del diablo"**: después de la respuesta,
un segundo agente (opus) la cuestiona específicamente. Dos perspectivas
para las decisiones que importan.

---

## La capa Soul (Alma)

Cada agente registrado en Rugol hereda automáticamente un stack de
capacidades que lo transforma de "un prompt con un modelo" en algo con
continuidad. No tienes que configurarlo — es el default de la plataforma.

1. **Identidad** — cada run arranca con "eres X, has corrido N veces
   antes, esto es lo que ya hemos trabajado juntos". El agente suena
   como él mismo entre runs porque siempre sabe quién es.
2. **Memoria proactiva** — el agente tiene tres herramientas que puede
   llamar por su cuenta: `save_memory`, `list_my_memories`,
   `forget_memory`. Lee reglas explícitas de *cuándo* guardar (hechos
   del usuario, feedback, estado del proyecto, referencias externas) y
   qué NO guardar. La memoria persiste entre runs como markdown plano
   en `agent-memory/`.
3. **(Roadmap) Despachador dual** — un clasificador en Haiku rutea
   cada request a Sistema 1 (rápido, con caché) o Sistema 2
   (deliberado, Opus, plan-then-execute). Kahneman, hecho ejecutable.
4. **(Roadmap) Archivo evolutivo** — cada system prompt de cada agente
   tiene un árbol de versiones, cada una validada empíricamente contra
   runs pasados. Inspirado en Darwin Gödel Machine (arXiv:2505.22954).
   Auto-mejora abierta, con humano siempre en el loop.

Diseño completo en
[`docs/adrs/ADR-006-soul-layer.md`](docs/adrs/ADR-006-soul-layer.md),
más ADR-007 y ADR-008 para los próximos sprints.

---

## Quickstart

**No hace falta instalar runtimes.** El instalador trae los suyos (un
Python aislado vía [uv](https://github.com/astral-sh/uv), y Node) — no
necesitás tener Python, Node ni Docker. Lo único que espera encontrar en la
máquina es **git** y **curl**, que macOS y la mayoría de las distros de Linux
ya traen; en Windows, instalá primero
[Git para Windows](https://git-scm.com/download/win). Una línea, después un wizard.

**Mac / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.sh | bash
```

**Windows** (PowerShell)
```powershell
iwr -useb https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.ps1 | iex
```

Después, desde cualquier terminal:

```bash
rugol setup      # auth + modelo + Telegram opcional (el wizard te guía)
rugol up         # construye, levanta core + dashboard, abre el navegador
```

**El auth, de las dos formas, corre headless.** Usá tu plan **Claude
Pro/Max** (el wizard corre `claude setup-token` y guarda un token long-lived,
sin costo por uso), o una **API key** dedicada (billing aislado). Todo corre
localmente bajo `~/.rugol`; nada tuyo sale de tu máquina.

Eso es todo — el dashboard abre en `http://localhost:3000` con siete
templates de proyecto listos para clonar. Todo lo que crees vive en
`~/.rugol`, así que actualizar nunca toca tus datos.

| Comando | Qué hace |
|---------|----------|
| `rugol setup` | Asistente inicial → escribe tu config |
| `rugol up` / `down` | Levanta / detiene todo |
| `rugol status` | Salud de los servicios de un vistazo |
| `rugol logs [core\|dashboard]` | Logs en vivo |
| `rugol doctor` | Verifica runtimes, puertos, config |
| `rugol update` | Actualiza y reconstruye (datos intactos) |
| `rugol uninstall` | Lo quita (pregunta antes de borrar datos) |

**Chateás desde el minuto uno.** `setup` te pregunta un agente por defecto
(`assistant`), así que si pones un token de Telegram le escribís al bot y
responde — sin `/bind`, sin menús. ¿Querés un agente específico en ese chat
después? `/bind <nombre>` o reasignalo en el dashboard. Token → chat, con un
panel de control completo esperándote cuando quieras profundidad.

<details>
<summary><b>Correr desde el código fuente (para devs)</b></summary>

Necesita Python 3.12+, Node 20+, y `claude /login` corrido una vez.

```bash
git clone https://github.com/EduardoMoraga/rugol.git
cd rugol

# Backend
python -m venv .venv
source .venv/bin/activate          # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r core/requirements.txt
cp .env.example .env               # USE_SUBSCRIPTION=true si usás Pro/Max
uvicorn core.main:app --host 127.0.0.1 --port 8000

# Frontend (otra terminal)
cd dashboard && pnpm install && pnpm dev
```

O directamente `docker compose up --build` desde la raíz.
</details>

---

## Las capas que ya están adentro · `v0.8.0-alpha`

Rugol se construyó en capas, cada una entregada como commit funcional
y testeado end-to-end. La versión actual incluye:

| Capa | Lo que aporta |
|------|---------------|
| **1** | Modelo project-first, migración no destructiva, /projects como home |
| **2** | Chat multi-turn con memoria entre turnos, markdown clickeable y syntax highlight |
| **3** | Lecciones vivas por proyecto + auto-trigger de self-improvement (Hermes-style) |
| **4** | Sistema 1/2 (selector de tipo de tarea) + abogado del diablo opcional |
| **5** | Tools editables por agente (whitelist) + dir picker en el Architect |
| **6** | Catálogo de 7 templates curados, clone con un click, auto-rename para duplicados |
| **7** | "Promover a lección" en cada respuesta y en cada self-improvement |
| **8** | MCP servers por agente (stdio/sse/http) — conectar Asana, Notion, Slack por agente |
| **9** | Ant farm con clusters por proyecto (visualización) |
| **10** | Onboarding emocional para usuarios nuevos |
| **11** | Health check extendido + DEVELOPMENT.md |
| **13** | Adapters Telegram + Slack con channel bindings + reply-on-completion |
| **14** | Reset a estado limpio (script + endpoint admin + botón en Settings) — instalar en otro PC en minutos |
| **15** | Toggle EN/ES en el nav rail (persistido en localStorage) |
| **16** | **Capa Soul — Sprint 1**: identidad + herramientas de memoria proactiva, cada agente las hereda automáticamente ([ADR-006](docs/adrs/ADR-006-soul-layer.md)) |
| **17** | **Capa Soul — Sprint 2**: despachador dual S1/S2 (clasificador Haiku) + plan-then-execute opcional ([ADR-007](docs/adrs/ADR-007-dual-track-dispatcher.md)) |
| **18** | **Capa Soul — Sprint 3**: archivo evolutivo por agente — proponer/validar/aceptar mutaciones del system prompt ([ADR-008](docs/adrs/ADR-008-evolutionary-archive.md)) |

Historia completa en [CHANGELOG.md](CHANGELOG.md). Detalle técnico en
[DEVELOPMENT.md](DEVELOPMENT.md) y los ADRs en [`docs/adrs/`](docs/adrs/).
Para instalar en una PC fresca ver [docs/install-on-new-pc.md](docs/install-on-new-pc.md).

---

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy async, SQLite (Postgres
  opcional), APScheduler, claude-agent-sdk.
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS v4, react-query,
  react-markdown, HTML5 Canvas para el ant farm.
- **Auth LLM**: subscripción Claude Pro/Max **o** API key — tu eligís
  por proyecto.
- **Local-first**: todo corre en tu PC. Sin telemetría por defecto.

---

## Modelo de seguridad

Leé esto antes de cambiar cómo se sirve Rugol.

Rugol es un **plano de control local de un solo usuario**, y adentro de ese
límite es deliberadamente permisivo: los agentes tienen acceso a shell y al
filesystem, porque meter mano en tus archivos reales es justamente el punto.
El corolario es que **la API no tiene autenticación** — cualquiera que alcance
el puerto puede correr un agente en tu máquina.

Eso es seguro bajo el supuesto que Rugol asume, y es el supuesto que los
defaults imponen:

- `rugol up` levanta el core y el dashboard solo en `127.0.0.1`.
- `docker compose up` publica ambos puertos solo en `127.0.0.1`.
- Nada se manda a ninguna parte. La telemetría está apagada salvo que la prendas.

Entonces: **no pongas Rugol en una red compartida ni en una IP pública.** Si
necesitás acceso remoto, tunelealo (SSH, Tailscale o similar) en vez de
cambiar la dirección de bind — no hay una capa de auth atrás que te salve. Si
corrés `uvicorn` a mano, mantené `--host 127.0.0.1`.

Los bugs de este tipo conviene reportarlos en privado: abrí un security
advisory en GitHub antes que un issue público.

---

## Para developers

Si vas a contribuir o forkear, lee primero
[**DEVELOPMENT.md**](DEVELOPMENT.md). Captura el stack, las reglas de
migración, los bugs conocidos (con sus workarounds), la cheatsheet de
arquitectura y un mapa de qué archivo toca qué capa.

Pull requests bienvenidos. Issues con casos de uso reales (especialmente
de personas no-técnicas) son aún más bienvenidos — son el material que
nos dice qué template falta.

---

## Roadmap próximo

- **Capa 8** — MCP servers por agente (conectar Asana, Notion, Slack,
  Gmail per-agente sin tocar el .env global).
- **Adapter Telegram + Slack** — chatear con cualquier agente desde el
  celular, ya con el adapter conectado por proyecto.
- **Templates en español adicional** — *"Mi negocio gastronómico",
  "Atención al cliente para mi tienda online"* y otros casos LATAM.
- **Instalador Windows `.bat`** — una sola línea para usuarios cero-código.

---

## Licencia

MIT. Haz lo que necesites.

---

<div align="center">

Hecho con cuidado por **Eduardo Moraga** ([eduardo.moraga.o@gmail.com](mailto:eduardo.moraga.o@gmail.com))
— economista, líder BI en Increxa, divulgador IA en LATAM.

Si esto te sirvió, contame en qué proyecto lo usaste. Eso es lo que mueve
la roadmap.

</div>
