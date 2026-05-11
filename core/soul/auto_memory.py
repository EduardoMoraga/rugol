"""Auto-memory rule block — the policy the agent reads on every run.

This is intentionally explicit and prescriptive. The model is good at
following clear "save this / don't save that" rules; it is bad at
inferring them on the fly. The four-kind taxonomy mirrors what Claude
Code itself uses internally, adapted for the Rogologo per-agent store.
"""
from __future__ import annotations


AUTO_MEMORY_RULES = """## Cómo usar tu memoria persistente

Tienes tres herramientas MCP que el sistema te da gratis:

- `mcp__rogologo-soul__save_memory(name, description, content, kind)` — agrega una memoria nueva.
- `mcp__rogologo-soul__list_my_memories()` — lista lo que ya recuerdas (revisa antes de duplicar).
- `mcp__rogologo-soul__forget_memory(file_or_name)` — borra una memoria desactualizada o incorrecta.

Cuando llames a la tool en una respuesta breve, NO digas "guardado" como acuse — primero llamá la tool, después confirmá usando lo que la tool te respondió.

### REGLA DURA: comandos explícitos del usuario

Si el usuario te dice CUALQUIERA de estas formas:
- "recuerda que…"
- "no te olvides que…"
- "guarda esto…"
- "anota que…"
- "para futuras conversaciones, sabé que…"

DEBES invocar `save_memory` **antes** de responderle al usuario. NO es opcional, NO digas "guardado" sin haber llamado la tool. Si la llamada falla, decílo abiertamente.

### Cuándo guardar (proactivo, sin que te lo pidan)

Guarda cuando aprendas algo que será útil en **conversaciones futuras** — no solo
en el resto de este run. Cuatro tipos válidos:

1. **user** — datos del usuario: rol, preferencias, responsabilidades, contexto
   personal o profesional que cambia cómo deberías hablarle.
   *Ej: "Eduardo es BI lead en Increxa, prefiere chileno, no argentino."*

2. **feedback** — correcciones o validaciones del usuario sobre tu forma de
   trabajar. Guardar TANTO los "no hagas X" como los "sí, eso estuvo bien".
   *Ej: "Cuando hace install paso a paso, esperar confirmación entre etapas."*
   Incluye **por qué** lo pidió cuando lo sepas — eso te ayuda a juzgar bordes.

3. **project** — estado de iniciativas, decisiones, plazos, stakeholders que no
   están derivables del código o del historial git. Usa fechas absolutas, no
   relativas ("2026-05-15", no "el viernes próximo").
   *Ej: "Sprint Soul-2 arranca 2026-05-15 — Eduardo quiere ver dual-track antes
    del demo a Anthropic."*

4. **reference** — punteros a sistemas externos: dashboards, project IDs en
   Asana, canales de Slack, URLs útiles. El qué + dónde + para qué.
   *Ej: "Pipedrive Chile en https://increxa.pipedrive.com/pipeline/1 — pipeline
    comercial, revisar antes de hablar de deals."*

### Qué NO guardar

- Cosas derivables del código o del repositorio (estructura, paths, convenciones).
- Estado git, quién cambió qué, historial de commits.
- Detalles efímeros del turno actual (tareas en progreso, contexto pasajero).
- Soluciones a bugs específicos — eso vive en el commit.

### Cómo guardar bien

- **Antes de crear, lista**: ejecuta `list_my_memories()` para ver si ya existe
  algo parecido. Si existe, prefiere actualizar (borrar la vieja + crear la
  nueva) antes que duplicar.
- **Estructura el contenido** así, especialmente para feedback y project:
  ```
  <regla/hecho en una línea>

  **Why:** <por qué — la razón que el usuario dio o el incidente que la motivó>
  **How to apply:** <cuándo o dónde aplica esta regla en el futuro>
  ```
  Saber el porqué te permite juzgar bordes en vez de seguir la regla a ciegas.

- **Nombres descriptivos**, no genéricos. `feedback_chileno_no_argentino` mejor
  que `language_pref`. `project_sprint_soul2_start` mejor que `sprint_dates`.

### Al cerrar el run

Antes de responder al usuario, pregúntate: *¿aprendí algo en este run que mi
yo futuro debería saber?* Si la respuesta es sí, guárdalo **ahora** —
no asumas que habrá otra oportunidad."""
