"""El contrato que todo motor tiene que cumplir.

Rugol dejó de estar casado con un solo CLI. Este módulo define la frontera:
cualquier motor que devuelva un `RunResult` sirve, y el resto de la plataforma
—orquestador, scheduler, Telegram, memoria, dashboard— no se entera de cuál
corrió.

Qué es un motor y qué no:

  - Un motor **lanza un CLI de agente** y traduce su salida a `RunResult`,
    publicando eventos en el bus mientras corre.
  - Un motor **no** decide qué agente correr, ni cuándo, ni con qué prompt.
    Eso es del orquestador.

Los dos motores que existen hoy difieren en cosas que importan y que no se
pueden esconder detrás de la interfaz:

  | | Claude | Codex |
  |---|---|---|
  | Herramientas propias de Rugol (memoria) | MCP in-process | no disponible |
  | Frenos de seguridad | hooks `PreToolUse` (preventivos) | sandbox nativo |
  | Sesión | `resume=<id>` de la SDK | `codex exec resume <uuid>` |

Por eso `RunRequest` lleva los campos comunes y cada motor ignora lo que no
puede honrar, dejándolo dicho en el log en vez de fallar en silencio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

EngineName = Literal["claude", "codex"]
ENGINES: tuple[str, ...] = ("claude", "codex")
DEFAULT_ENGINE: EngineName = "claude"


@dataclass
class RunResult:
    """Lo que toda corrida devuelve, sin importar el motor."""

    final_text: str
    session_id: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    files_generated: list[Path] = field(default_factory=list)
    # Qué motor la corrió. Se persiste para que la vista de una corrida no
    # mienta cuando un agente cambia de motor entre una y otra.
    engine: str = DEFAULT_ENGINE


@runtime_checkable
class Engine(Protocol):
    """Un motor de ejecución. `name` es lo que va en el frontmatter del agente."""

    name: str

    async def run(self, **kwargs) -> RunResult: ...


def normalize_engine(value: str | None) -> EngineName:
    """Frontmatter → motor válido. Un valor desconocido cae al default con log.

    Ser permisivo acá es deliberado: un typo en un `.md` no debe dejar a un
    agente sin poder correr.
    """
    import logging

    raw = (value or "").strip().lower()
    if not raw:
        return DEFAULT_ENGINE
    if raw in ENGINES:
        return raw  # type: ignore[return-value]
    aliases = {
        "claude-code": "claude",
        "anthropic": "claude",
        "openai": "codex",
        "codex-cli": "codex",
        "gpt": "codex",
    }
    if raw in aliases:
        return aliases[raw]  # type: ignore[return-value]
    logging.getLogger(__name__).warning(
        "motor '%s' desconocido en el frontmatter — uso '%s'. Válidos: %s",
        value, DEFAULT_ENGINE, ", ".join(ENGINES),
    )
    return DEFAULT_ENGINE
