<div align="center">

# Rogologo

**El centro de operaciones open-source para tus agentes Claude Code.**

Programalos. Chateá con ellos desde Telegram y Slack. Mirá cómo trabajan en un ant-farm 2D.
Una PC Windows. Un comando Docker. Cero vendor lock-in.

[Quickstart](#quickstart) · [Por qué](#por-qué-rogologo) · [Arquitectura](ARCHITECTURE.md) · [Roadmap](ROADMAP.md) · [English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Next.js%2015-blue)]()
[![Status](https://img.shields.io/badge/status-alpha-orange)]()

</div>

---

## Por qué Rogologo

Si construís con Claude Code seguramente tenés una carpeta `.claude/agents/`
llena de subagentes finamente tuneados — y la sensación de que podrían estar
haciendo mucho más. Te gustaría:

- Correrlos en horarios fijos (un agente de "marca personal" que postea cada lunes).
- Chatear con ellos desde el celular sin abrir VS Code.
- Ver cuál está ocupado, cuál falló anoche, cuál está dormido.
- Que varios agentes conversen entre ellos dentro de un canal de Slack.
- Que mejoren sus propios prompts en base a sus corridas pasadas.

Rogologo es el control plane que falta para eso. Corre local en una PC Windows
(sin nube, sin SaaS), lee tus `.claude/agents/` existentes y te da:

- Un **dashboard** con estado vivo, historial de runs, costos, logs.
- Un **scheduler** con triggers cron y tareas one-shot.
- **Adaptadores Telegram y Slack** que rutean mensajes al agente correcto.
- Una **vista ant-farm** — escena 2D donde cada agente es un sprite que
  despierta y se mueve cuando trabaja. Goce visual puro.
- Una **ontología compartida** — grafo de conceptos, entidades y relaciones
  que todos los agentes leen y escriben.
- Un **loop de auto-mejora** — después de cada run el agente reflexiona,
  propone ediciones a su propio `.md` y espera tu aprobación.

## Quickstart

### Requisitos

- Windows 10/11 (soporte Linux & macOS tracked en [#3](https://github.com/eduardomoraga/rogologo/issues/3))
- Cuenta [Anthropic](https://console.anthropic.com) — suscripción Pro/Max **o** API key
- 8 GB RAM, 10 GB disco

### Instalación (una línea)

```powershell
git clone https://github.com/eduardomoraga/rogologo.git
cd rogologo
.\installer\install.bat
```

El wizard:
1. Chequea e instala **Docker Desktop**, **Node.js**, **Claude Code CLI** si faltan
2. Te guía por `claude /login` (usa tu suscripción, sin cargos de API)
3. Opcionalmente toma un **token de bot Telegram** y **token Slack**
4. Genera `.env` y corre `docker compose up -d`
5. Abre el dashboard en <http://localhost:3000>

### Agregá tu primer agente

Tirá cualquier `.md` con frontmatter en `agents/`:

```markdown
---
name: brand-architect
model: opus
description: Postea en LinkedIn cada lunes con tomas curadas.
---

Sos el estratega de marca personal de Eduardo. Cada lunes a las 9 AM...
```

Aparece en el dashboard en 5 segundos. Clic en "Schedule", elegí un cron, listo.

## Qué hay adentro

```
core/        Backend FastAPI (registry, scheduler, adapters, ontología)
dashboard/   Frontend Next.js 15 + Tailwind v4 (con ant-farm react-pixi)
installer/   Wizard Windows (.bat + .ps1)
docs/        Arquitectura, ADRs, screenshots
```

Ver [ARCHITECTURE.md](ARCHITECTURE.md) para el deep-dive.

## Estado

**Alpha.** La plomería funciona. El producto se está puliendo. Dale star al
repo para seguir el camino a v1.0 ([ROADMAP.md](ROADMAP.md)).

## Construido sobre

- [Anthropic Claude](https://www.anthropic.com/claude) y [Claude Code](https://github.com/anthropics/claude-code)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Next.js](https://nextjs.org), [shadcn/ui](https://ui.shadcn.com), [react-pixi](https://github.com/pixijs/pixi-react)

## Licencia

MIT. Hacé lo que quieras, no nos eches la culpa.

---

Hecho por [Eduardo Moraga](https://github.com/eduardomoraga) ·
Inspirado por [OpenClaw](https://docs.openclaw.ai), [Engram](https://github.com/cpacker/MemGPT)
y la fricción diaria de correr 30 agentes a mano.
