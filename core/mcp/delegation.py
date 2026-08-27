"""Que un agente pueda pedirle trabajo a otro — con frenos.

Hasta ahora "gugol coordina al equipo" era una descripción, no un mecanismo. Las
seis herramientas que Rugol le daba a sus agentes eran todas de memoria; ninguna
llamaba a otro agente. Un agente que dice coordinar y hace todo él solo no
coordina: trabaja mucho.

Delegar es la clase de capacidad que se rompe sola si se agrega sin límites. Los
tres frenos de acá no son paranoia, son las tres formas conocidas de que esto
termine mal:

**Profundidad.** A → B → C → D es una cadena que nadie pidió y que cuesta plata
en cada eslabón. Un agente llamado por otro agente NO puede delegar. Dos niveles
—vos pedís, el coordinador reparte— cubren el caso real; el tercero es casi
siempre un error de diseño del prompt.

**Ciclos.** A llama a B, B llama a A. Sin memoria de la cadena esto no termina
nunca. Se lleva la lista de quién ya está en la cadena y se rechaza volver a
entrar. Incluye llamarse a sí mismo, que es el ciclo más corto y el más fácil de
escribir sin querer.

**Cantidad.** Un coordinador con un prompt entusiasta puede repartirle la misma
tarea a los ocho agentes del proyecto. El tope por corrida raíz existe para que
eso sea un error acotado y no una factura.

Y uno que no es un freno sino una decisión: la respuesta del delegado vuelve
como TEXTO al que preguntó. No comparte sesión, no comparte memoria, no puede
escribir en la libreta del otro. Es un encargo, no una fusión.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Dos niveles: vos → coordinador → especialista. El tercero casi siempre es un
# prompt mal escrito, no una necesidad.
MAX_DEPTH = 2
# Delegaciones por corrida raíz. Un coordinador entusiasta con ocho agentes en
# el proyecto puede repartir ocho veces la misma tarea sin darse cuenta.
MAX_PER_ROOT = 5
# Un delegado colgado no puede dejar esperando al que preguntó para siempre.
TIMEOUT_SECONDS = 600

# Cadena viva por corrida raíz: quiénes ya participaron y cuántas van.
# En memoria a propósito — muere con el proceso, igual que las corridas.
_CADENAS: dict[str, dict] = {}


class DelegationError(Exception):
    """Un freno se activó. El motivo va adentro, para que el modelo lo lea."""


def chain_key(root_run_id: int | None, caller: str) -> str:
    """La identidad de una cadena de delegación."""
    return f"{root_run_id or 0}:{caller}"


def register_root(key: str, caller: str, depth: int = 1) -> None:
    _CADENAS.setdefault(key, {"agents": {caller.lower()}, "count": 0, "depth": depth})


def check(key: str, caller: str, target: str) -> None:
    """¿Se puede delegar? Si no, levanta con el motivo escrito para el modelo."""
    objetivo = (target or "").strip().lower()
    if not objetivo:
        raise DelegationError("Falta el nombre del agente.")
    if objetivo == (caller or "").strip().lower():
        raise DelegationError(
            "Un agente no puede delegarse a sí mismo — resolvelo directamente."
        )
    estado = _CADENAS.get(key)
    if estado is None:
        register_root(key, caller)
        estado = _CADENAS[key]
    if estado["depth"] >= MAX_DEPTH:
        raise DelegationError(
            f"Ya estás en una tarea delegada (nivel {estado['depth']}). "
            "Un agente llamado por otro no puede delegar de nuevo: resolvé o "
            "explicá qué falta."
        )
    if objetivo in estado["agents"]:
        raise DelegationError(
            f"'{target}' ya está en esta cadena de delegación — sería un ciclo."
        )
    if estado["count"] >= MAX_PER_ROOT:
        raise DelegationError(
            f"Llegaste al máximo de {MAX_PER_ROOT} delegaciones para esta tarea. "
            "Sintetizá con lo que ya tenés."
        )


def note(key: str, target: str) -> None:
    """Anota una delegación aceptada."""
    estado = _CADENAS.setdefault(key, {"agents": set(), "count": 0, "depth": 1})
    estado["agents"].add((target or "").strip().lower())
    estado["count"] += 1


def child_state(key: str, target: str) -> dict:
    """El estado que hereda el delegado: un nivel más abajo, misma cadena."""
    padre = _CADENAS.get(key) or {"agents": set(), "count": 0, "depth": 1}
    return {
        "agents": set(padre["agents"]) | {(target or "").strip().lower()},
        "count": padre["count"],
        "depth": padre["depth"] + 1,
    }


def adopt(key: str, estado: dict) -> None:
    _CADENAS[key] = estado


def forget(key: str) -> None:
    _CADENAS.pop(key, None)


async def delegate(
    *,
    caller: str,
    target: str,
    prompt: str,
    root_run_id: int | None,
) -> str:
    """Corre `target` con `prompt` y devuelve su respuesta como texto.

    Espera al delegado: el que preguntó necesita la respuesta para seguir. Por
    eso el timeout no es opcional — sin él, un delegado colgado cuelga también
    a quien lo llamó, y desde afuera parece que el coordinador se murió.
    """
    key = chain_key(root_run_id, caller)
    check(key, caller, target)

    from sqlalchemy import select

    from core.db import async_session_factory
    from core.db.models import Agent, Run
    from core.runner.orchestrator import RunRequest, get_orchestrator

    async with async_session_factory() as session:
        existe = (await session.execute(
            select(Agent).where(Agent.name == target)
        )).scalar_one_or_none()
        if existe is None:
            nombres = [
                a.name for a in (await session.execute(select(Agent))).scalars().all()
            ]
            raise DelegationError(
                f"No existe el agente '{target}'. Hay: {', '.join(sorted(nombres))}"
            )

    note(key, target)
    hijo = child_state(key, target)
    orq = get_orchestrator()
    run_id = await orq.enqueue(
        RunRequest(
            agent_name=target,
            prompt=prompt,
            source="delegation",
        )
    )
    # El delegado hereda la cadena: así SUS frenos saben que ya está a nivel 2.
    adopt(chain_key(root_run_id, target), hijo)
    logger.info(
        "delegación: %s → %s (corrida %s, nivel %s)", caller, target, run_id, hijo["depth"]
    )

    try:
        texto = await asyncio.wait_for(_wait_for(run_id), timeout=TIMEOUT_SECONDS)
    except TimeoutError:
        orq.cancel(run_id)
        raise DelegationError(
            f"'{target}' no respondió en {TIMEOUT_SECONDS // 60} minutos — la corté."
        ) from None
    finally:
        forget(chain_key(root_run_id, target))

    async with async_session_factory() as session:
        fila = await session.get(Run, run_id)
        if fila is not None and fila.status == "failed":
            raise DelegationError(
                f"'{target}' falló: {fila.error_message or 'sin detalle'}"
            )
    return texto


async def _wait_for(run_id: int) -> str:
    """Espera a que la corrida termine y devuelve su texto final."""
    from core.db import async_session_factory
    from core.db.models import TERMINAL_RUN_STATUSES, Run

    while True:
        async with async_session_factory() as session:
            fila = await session.get(Run, run_id)
            if fila is not None and fila.status in TERMINAL_RUN_STATUSES:
                return (fila.final_text or "").strip() or "(sin respuesta)"
        await asyncio.sleep(1.5)
