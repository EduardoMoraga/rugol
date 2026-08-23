"""Elegir el motor. Un solo lugar, para que el orquestador no sepa de motores.

El orquestador arma todo el contexto de una corrida —persona, misión,
memoria, tools— y llama a `run_with_engine`. Acá se decide qué CLI la ejecuta
y se traduce el contexto a lo que ese CLI puede recibir.

La traducción no es simétrica y no se disimula:

  claude  Recibe todo: el contexto va como `append` al system prompt del
          preset, y las tools de Rugol entran como MCP in-process.
  codex   No tiene `append` de system prompt ni MCP in-process. El contexto
          se colapsa en un bloque delimitado al principio del prompt, y las
          tools de memoria simplemente no están. Se avisa una vez por corrida.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.runner.base import DEFAULT_ENGINE, RunResult, normalize_engine

logger = logging.getLogger(__name__)


def _collapse_context(
    *,
    agent_body: str | None,
    soul_context: str | None,
    project_context: str | None,
    skills_catalogue: str | None = None,
) -> str | None:
    """Las capas de contexto en un solo bloque, en el mismo orden que usa el
    motor Claude: quién soy → qué procedimientos tengo → cómo recuerdo → misión."""
    parts = [
        p.strip()
        for p in (agent_body, skills_catalogue, soul_context, project_context)
        if p and p.strip()
    ]
    return "\n\n".join(parts) if parts else None


async def run_with_engine(
    *,
    engine: str | None,
    agent_name: str,
    prompt: str,
    workspace_dir: Path,
    model: str,
    session_id: str | None = None,
    run_id: int | None = None,
    tools: list[str] | None = None,
    project_context: str | None = None,
    mcp_servers: dict | None = None,
    soul_context: str | None = None,
    soul_mcp_server=None,
    soul_tool_names: tuple[str, ...] = (),
    agent_body: str | None = None,
    telegram_mcp_server=None,
    telegram_tool_names: tuple[str, ...] = (),
    skills_catalogue: str | None = None,
) -> RunResult:
    """Corre el agente con el motor que le corresponde y devuelve `RunResult`."""
    chosen = normalize_engine(engine)

    if chosen == "codex":
        from core.config import get_settings
        from core.runner.codex_runner import run as codex_run

        timeout = float(getattr(get_settings(), "CODEX_TIMEOUT_SECONDS", 0) or 0) or None
        if soul_mcp_server is not None or telegram_mcp_server is not None:
            logger.info(
                "codex: el agente %s tiene tools in-process de Rugol (memoria/telegram) "
                "que este motor no puede exponer — corre sin ellas",
                agent_name,
            )
        return await codex_run(
            agent_name=agent_name,
            prompt=prompt,
            workspace_dir=workspace_dir,
            model=model,
            session_id=session_id,
            run_id=run_id,
            system_context=_collapse_context(
                agent_body=agent_body,
                soul_context=soul_context,
                project_context=project_context,
                skills_catalogue=skills_catalogue,
            ),
            timeout_seconds=timeout,
        )

    if chosen != DEFAULT_ENGINE:  # pragma: no cover — normalize_engine ya filtró
        logger.warning("motor '%s' sin implementación — uso %s", chosen, DEFAULT_ENGINE)

    from core.runner.claude_runner import run_agent

    return await run_agent(
        agent_name=agent_name,
        prompt=prompt,
        workspace_dir=workspace_dir,
        model=model,
        session_id=session_id,
        run_id=run_id,
        tools=tools,
        project_context=project_context,
        mcp_servers=mcp_servers,
        soul_context=soul_context,
        soul_mcp_server=soul_mcp_server,
        soul_tool_names=soul_tool_names,
        agent_body=agent_body,
        telegram_mcp_server=telegram_mcp_server,
        telegram_tool_names=telegram_tool_names,
        skills_catalogue=skills_catalogue,
    )
