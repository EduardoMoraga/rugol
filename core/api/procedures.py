"""Soul-4 — los métodos compilados, y si de verdad están abaratando el trabajo.

Este endpoint existe para una sola cosa: hacer FALSABLE la tesis del producto.
Y por eso mismo tiene que medir lo que dice medir.

**La versión anterior no lo hacía, y el error importa.** Comparaba el primer
tercio contra el último tercio de las corridas que YA aplicaban un método. Eso
responde "¿este método se abarató con el uso?", que es una pregunta razonable
pero no es la del producto. La del producto es otra:

    ¿Resolver esto costaba System 2, y ahora cuesta System 1?

Y la corrida que contesta el "antes" —la deliberada, la cara, la que descubrió
el método— quedaba FUERA de la comparación: tiene `procedure` en NULL, porque
cuando corrió el método todavía no existía. Se estaba midiendo la pendiente
después del salto, y presentándola como el salto.

Ahora la corrida que parió el método se anota (`Run.compiled_procedure`) y es la
línea base. La comparación pasa a ser la correcta: **lo que costó descubrirlo,
contra lo que cuesta aplicarlo.**

Lo que este endpoint sigue sin poder afirmar, y por eso no lo afirma: que la
respuesta sea igual de BUENA. Mide costo, no calidad. Un método que abarata un
40% y empeora la respuesta es una pérdida disfrazada de ganancia, y ese hueco se
cierra con outcomes, no acá.
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import or_, select

from core.db import async_session_factory
from core.db.models import Agent, Run
from core.memory.store import list_procedures

router = APIRouter(prefix="/procedures", tags=["soul"])

# Aplicaciones mínimas para hablar de tendencia entre aplicaciones. Una corrida
# rápida por suerte no es una curva.
_MIN_MUESTRA = 6


def _promedio(valores: list[float]) -> float:
    return round(sum(valores) / len(valores), 2) if valores else 0.0


def _tokens(r: Run) -> float:
    return float((r.input_tokens or 0) + (r.output_tokens or 0))


def _segundos(r: Run) -> float | None:
    if not (r.ended_at and r.started_at):
        return None
    return (r.ended_at - r.started_at).total_seconds()


def _resumen(runs: list[Run]) -> dict:
    segundos = [s for s in (_segundos(r) for r in runs) if s is not None]
    return {
        "runs": len(runs),
        "tokens": _promedio([_tokens(r) for r in runs]),
        "cost_usd": round(sum(float(r.cost_usd or 0.0) for r in runs) / max(1, len(runs)), 5),
        "seconds": _promedio(segundos),
    }


def _tramo(runs: list[Run], primeros: bool) -> dict:
    """El primer o el último tercio. Tercios y no primera-contra-última:
    una sola corrida afortunada no puede parecer una tendencia."""
    corte = max(1, len(runs) // 3)
    return _resumen(runs[:corte] if primeros else runs[-corte:])


def _delta(antes: float, ahora: float) -> float | None:
    return round((ahora - antes) / antes * 100, 1) if antes else None


@router.get("")
async def list_procedures_with_evidence() -> list[dict]:
    """Cada método compilado, con la evidencia de si está sirviendo."""
    salida: list[dict] = []
    async with async_session_factory() as session:
        agentes = (await session.execute(select(Agent))).scalars().all()
        for agente in agentes:
            for mem in list_procedures(agente.name):
                # Una sola consulta trae las dos cosas: la corrida que lo parió
                # y las que lo aplicaron.
                runs = (await session.execute(
                    select(Run)
                    .where(Run.agent_id == agente.id)
                    .where(Run.status == "completed")
                    .where(or_(
                        Run.procedure == mem.name,
                        Run.compiled_procedure == mem.name,
                    ))
                    .order_by(Run.id)
                )).scalars().all()

                origen = [r for r in runs if r.compiled_procedure == mem.name]
                aplicadas = [r for r in runs if r.procedure == mem.name]

                fila = {
                    "agent": agente.name,
                    "name": mem.name,
                    "description": mem.description,
                    "created_at": mem.created_at,
                    "applied_runs": len(aplicadas),
                    # El salto que el producto promete: descubrirlo vs aplicarlo.
                    "leap": None,
                    # La pendiente después del salto: ¿sigue mejorando con el uso?
                    "trend": None,
                }

                # EL SALTO. Sólo se puede afirmar si conocemos la corrida
                # original. Sin ella no hay "antes", y antes se inventaba uno.
                if origen and aplicadas:
                    antes = _resumen(origen)
                    ahora = _resumen(aplicadas)
                    fila["leap"] = {
                        "discovering": antes,
                        "applying": ahora,
                        "tokens_delta_pct": _delta(antes["tokens"], ahora["tokens"]),
                        "seconds_delta_pct": _delta(antes["seconds"], ahora["seconds"]),
                    }

                # LA PENDIENTE, entre aplicaciones. Es otra pregunta y se
                # reporta aparte para no volver a confundirlas.
                if len(aplicadas) >= _MIN_MUESTRA:
                    antes, ahora = _tramo(aplicadas, True), _tramo(aplicadas, False)
                    fila["trend"] = {
                        "first": antes,
                        "recent": ahora,
                        "tokens_delta_pct": _delta(antes["tokens"], ahora["tokens"]),
                    }
                salida.append(fila)
    salida.sort(key=lambda f: (-f["applied_runs"], f["name"]))
    return salida
