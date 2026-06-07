"""Soul-1.5 — End-of-run memory checkpoint.

Without an explicit "stop and reflect" trigger, the model rarely calls
save_memory mid-run because it's focused on responding. This module
fires a cheap follow-up run after every successful primary run, asking
the model to evaluate the just-finished interaction and persist anything
durable as memory.

Modelled on Claude Code's own Stop hook: "before closing, evaluate
whether memory should be saved." Without this, Soul-1 (the tool + rules)
is necessary but not sufficient — the agent has the tool but never a
moment to use it.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.config import get_settings
from core.llm_models import HAIKU
from core.soul.tools import SOUL_TOOL_NAMES, build_soul_mcp_server

logger = logging.getLogger(__name__)


_CHECKPOINT_PROMPT = """Acabás de terminar un run. Antes de cerrar, evaluá si aprendiste algo durable que tu yo futuro debería saber.

## Tu identidad
Eres **{agent_name}**.

## El run que acaba de terminar
**Usuario dijo:**
{user_prompt}

**Tú respondiste:**
{agent_response}

## Tu evaluación

Revisá la interacción y guardá UNA o MÁS memorias **solo si aplica de verdad**. Cuatro tipos válidos:

1. **user** — un hecho durable sobre el usuario (su rol, preferencia, contexto) que apareció recién y vale para conversaciones futuras.
2. **feedback** — corrección o validación explícita del usuario sobre tu forma de trabajar. Guardá tanto los "no hagas X" como los "sí, así me gustó".
3. **project** — estado de iniciativa, decisión, plazo, stakeholder mencionado.
4. **reference** — puntero a sistema externo: URL, dashboard, ID, canal.

**REGLAS DURAS**:
- NO inventes memorias para parecer útil.
- NO guardes nada que el agente ya sabe de su propio entrenamiento.
- NO guardes estado pasajero del turno.
- Si el run fue una pregunta operativa trivial ("qué día es", "cómo estás") y no hubo aprendizaje real, respondé exactamente la frase `NO_MEMORY_NEEDED` y terminá ahí, sin llamar herramientas.

Si SÍ vale guardar algo, llamá la tool `save_memory` UNA VEZ por cada hallazgo claro. Los argumentos deben ser:
- `name`: snake_case descriptivo, ej. `user_prefiere_respuestas_cortas`.
- `description`: una línea, lo que verás en el índice.
- `content`: dos a cinco líneas. Si es feedback/project, estructurá como:
  ```
  <regla o hecho>

  **Why:** <por qué — la razón que el usuario dio>
  **How to apply:** <cuándo / dónde aplica en el futuro>
  ```
- `kind`: uno de `user|feedback|project|reference`.

Para conectar esta memoria con otras, incluí wikilinks `[[nombre_de_otra_memoria]]` dentro del `content`. Si no estás seguro de los nombres exactos, llamá `list_my_memories` primero. Enlazar memorias relacionadas teje tu memoria como una red navegable (grafo Obsidian), no una lista plana.

Después de llamar la tool (o de decir NO_MEMORY_NEEDED), terminá. No expliques al usuario lo que guardaste — esto es housekeeping interno.
"""


async def run_checkpoint(
    *,
    agent_name: str,
    user_prompt: str,
    agent_response: str,
    workspace_dir: Path,
) -> bool:
    """Fire a checkpoint run that evaluates whether to persist memory.

    Returns True when the checkpoint ran (even if it saved nothing),
    False when it was skipped or failed.

    The checkpoint:
    - Uses Haiku (cheapest model) — the evaluation is structured.
    - Has the rugol-soul MCP server attached so save_memory works.
    - Is best-effort — failures are logged but never propagate.
    """
    settings = get_settings()
    if not settings.SOUL_AUTO_CHECKPOINT_ENABLED:
        return False
    if not (user_prompt or "").strip() or not (agent_response or "").strip():
        return False

    # Lazy import to avoid a circular dependency with the runner.
    from core.runner.claude_runner import run_agent

    prompt = _CHECKPOINT_PROMPT.format(
        agent_name=agent_name,
        user_prompt=(user_prompt or "").strip()[:2000],
        agent_response=(agent_response or "").strip()[:4000],
    )

    soul_server = build_soul_mcp_server(agent_name)

    try:
        result = await run_agent(
            agent_name=f"{agent_name}-checkpoint",
            prompt=prompt,
            workspace_dir=workspace_dir,
            model=HAIKU,
            tools=None,  # let the preset surface the soul tools naturally
            soul_mcp_server=soul_server,
            soul_tool_names=SOUL_TOOL_NAMES,
            # We deliberately skip soul_context here — the checkpoint
            # already has identity + rules embedded in its prompt, and
            # we don't want to recurse the world-state / memory blocks
            # into a meta-evaluation.
        )
    except Exception:
        logger.exception(
            "checkpoint for agent=%s failed (best-effort, swallowing)",
            agent_name,
        )
        return False

    text = (result.final_text or "").strip()
    if "NO_MEMORY_NEEDED" in text and "save_memory" not in text:
        logger.info("checkpoint for %s: no memory saved (NO_MEMORY_NEEDED)", agent_name)
    else:
        logger.info(
            "checkpoint for %s finished (cost=$%.4f, tokens=%d)",
            agent_name, result.cost_usd or 0.0,
            (result.input_tokens or 0) + (result.output_tokens or 0),
        )
    return True
