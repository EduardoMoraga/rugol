<div align="center">

# Rogologo

**Tu sistema operativo de agentes IA, hecho para personas que piensan en proyectos, no en tecnología.**

Una sala de control local donde tus equipos de agentes Claude trabajan por vos —
tu marca, tu día a día, ayudar a tu hija a estudiar, tu pipeline comercial.

[Quickstart](#quickstart) · [Por qué Rogologo](#por-qué-rogologo) · [Casos reales](#casos-reales) · [Cómo funciona](#cómo-funciona) · [English](README.md)

</div>

---

> **"La vida es la sumatoria de proyectos. Vos sos el CEO; ellos ejecutan."**

Rogologo cambia el paradigma. No pensás "qué agente creo". Pensás
**qué proyecto necesito**: tu asistente personal, tu marca, ayudar a
tu hija a estudiar biología jugando, tu pipeline de ventas. Cada
proyecto se arma con su propio equipo de agentes especialistas, su
misión escrita y sus reglas vivas. Vos sos el CEO del proyecto;
los agentes son el departamento.

---

## Por qué Rogologo

### Hecho por alguien de negocio, no por un dev

Soy economista. Lidero proyectos de Business Intelligence en LATAM.
Vi cómo "agentic AI" estaba quedando atrapado en un lenguaje técnico
que excluye a las personas comunes — las mismas personas para las
que la herramienta puede cambiar la vida.

Rogologo nace de esa frustración. Detrás del código (que armé con
Claude Code, claro), las decisiones de producto vienen de otro lado:
**economía conductual, problemas reales de productividad, vida
cotidiana**.

### El paradigma project-first

| Otras plataformas | Rogologo |
|---|---|
| Lista plana de agentes sueltos | Proyectos como departamentos con misión |
| Vos decidís qué modelo usar (haiku/sonnet/opus) | Vos elegís el **tipo de tarea** (heurística / pensar / deliberar); el sistema rutea |
| Agente que actúa solo | Opcional: abogado del diablo cuestiona antes de actuar |
| Memoria por agente o ninguna | Lecciones vivas por proyecto que el equipo lee antes de cada tarea |
| Templates técnicos | Templates emocionales: "asistente personal", "mi hija aprende jugando" |

### Tres principios de economía conductual encarnados en software

| Principio | Cómo aparece en Rogologo |
|---|---|
| **Sistema 1 vs Sistema 2** (Kahneman) | El usuario no piensa en modelos. Elige *Heurística* (haiku, rápido), *Pensar* (modelo del agente) o *Deliberar* (opus, decisiones caras de revertir). |
| **Ruido** (Kahneman/Sunstein) | Antes de decisiones importantes, el "Abogado del diablo" (opus) cuestiona la respuesta primaria. Dos perspectivas, vos decidís. |
| **Sesgos** | Cada proyecto mantiene una lista viva de *lecciones* (lessons / biases / facts). Cada agente del equipo las lee antes de cada run. Lo que aprendiste de la mala queda como anclaje permanente. |

---

## Casos reales

### "Mi hija aprende jugando"

Mi hija de 9 años tenía prueba de biología. En 5 minutos, dos agentes
(designer Haiku + builder Sonnet) generaron un mini-juego HTML+JS sobre
la fotosíntesis. Sin librerías, sin instalación, doble click y a jugar.
Ella aprendió sin darse cuenta. Estudió mientras se reía.

Es un template incluido en Rogologo. Una mamá que solo usó ChatGPT puede
clonarlo, escribir "el tema de esta semana es células" y tener un juego
nuevo en minutos.

### "Mi marca personal"

Tres agentes que cuidan la voz pública: brand-architect (Opus, decide qué
es On-brand), content-editor (escribe los posts), market-analyst (mide qué
resuena). Lecciones vivas como *"nunca usar 'leverage'"* o *"cero hype"*
quedan inyectadas en cada run, así el equipo no se desvía aunque vos no
estés mirando.

### "Pipeline comercial"

Para freelancers y founders que llevan ventas en una hoja de cálculo:
prospector + qualifier + follower-upper. Schedule diario que no deja
caer ningún follow-up activo. Honestidad sobre fit: si no somos para el
cliente, lo dice.

### "Asistente personal"

Brief diario por la mañana, triage de inbox, captura de día por la noche.
El equipo invisible que cuida tu día.

### "Investigador de un tema"

Cuando tenés que dominar algo nuevo en una semana: researcher recopila
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

## Quickstart

**Pre-requisitos**: Windows 10/11 (Mac/Linux funcionan, instaladores
están en camino), Python 3.12+, Node 20+, Docker opcional, y haber
corrido `claude /login` una vez para autenticar.

```bash
# Clonar
git clone https://github.com/<tu-fork>/rogologo.git
cd rogologo

# Backend (Python venv)
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # PowerShell
# source .venv/bin/activate     # bash
pip install -r core/requirements.txt
cp .env.example .env             # ajustá USE_SUBSCRIPTION=true si usás Pro/Max
uvicorn core.main:app --host 127.0.0.1 --port 8000

# Frontend (otra terminal)
cd dashboard
pnpm install
pnpm dev
```

Abrí `http://localhost:3000`. Si es la primera vez, vas a ver una
pantalla emocional con cinco templates listos. Click en uno → personalizá
si querés → deployá. Tu equipo ya está funcionando.

---

## Las capas que ya están adentro

Rogologo se construyó en capas, cada una entregada como commit funcional
y testeado end-to-end. La versión actual incluye:

| Capa | Lo que aporta |
|------|---------------|
| **1** | Modelo project-first, migración no destructiva, /projects como home |
| **2** | Chat multi-turn con memoria entre turnos, markdown clickeable y syntax highlight |
| **3** | Lecciones vivas por proyecto + auto-trigger de self-improvement (Hermes-style) |
| **4** | Sistema 1/2 (selector de tipo de tarea) + abogado del diablo opcional |
| **5** | Tools editables por agente (whitelist) + dir picker en el Architect |
| **6** | Catálogo de 5 templates curados, clone con un click, auto-rename para duplicados |
| **7** | "Promover a lección" en cada respuesta y en cada self-improvement |
| **9** | Ant farm con clusters por proyecto (visualización) |
| **10** | Onboarding emocional para usuarios nuevos |
| **11** | Health check extendido + DEVELOPMENT.md |

Detalle técnico: ver [DEVELOPMENT.md](DEVELOPMENT.md) y los ADRs en
[`docs/adrs/`](docs/adrs/).

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

## Para developers

Si vas a contribuir o forkear, leé primero
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

MIT. Hacé lo que necesites.

---

<div align="center">

Hecho con cuidado por **Eduardo Moraga** ([eduardo.moraga.o@gmail.com](mailto:eduardo.moraga.o@gmail.com))
— economista, líder BI en Increxa, divulgador IA en LATAM.

Si esto te sirvió, contame en qué proyecto lo usaste. Eso es lo que mueve
la roadmap.

</div>
