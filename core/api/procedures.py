"""Soul-4 — los métodos compilados, y si de verdad están abaratando el trabajo.

Este endpoint existe para una sola cosa: hacer FALSABLE la tesis del producto.

"Mi agente aprende y se vuelve más rápido" es una frase que nadie puede
contradecir, y por eso no significa nada. Lo que sí significa algo es: esta
familia de tarea costaba 18.000 tokens la primera vez y cuesta 6.000 ahora,
sobre 23 corridas. Si el número no baja, el bucle no funciona, y hay que saberlo.

Cada corrida ya guarda tokens, costo, duración y qué método aplicó. Acá se
agrupa por método y se compara el primer tercio contra el último.
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from core.db import async_session_factory
from core.db.models import Agent, Run
from core.memory.store import list_procedures

router = APIRouter(prefix="/procedures", tags=["soul"])


def _promedio(valores: list[float]) -> float:
    return round(sum(valores) / len(valores), 2) if valores else 0.0


def _tramo(runs: list[Run], primeros: bool) -> dict:
    """El primer o el último tercio de las corridas de un método.

    Tercios y no "primera vs última": una sola corrida rápida por suerte no
    puede parecer una tendencia. Con menos de 6 corridas no se reporta nada.
    """
    corte = max(1, len(runs) // 3)
    tramo = runs[:corte] if primeros else runs[-corte:]
    return {
        "runs": len(tramo),
        "tokens": _promedio([float((r.input_tokens or 0) + (r.output_tokens or 0)) for r in tramo]),
        "cost_usd": round(sum(float(r.cost_usd or 0.0) for r in tramo) / max(1, len(tramo)), 5),
        "seconds": _promedio([
            (r.ended_at - r.started_at).total_seconds()
            for r in tramo if r.ended_at and r.started_at
        ]),
    }


@router.get("")
async def list_procedures_with_evidence() -> list[dict]:
    """Cada método compilado, con la evidencia de si está sirviendo."""
    salida: list[dict] = []
    async with async_session_factory() as session:
        agentes = (await session.execute(select(Agent))).scalars().all()
        for agente in agentes:
            for mem in list_procedures(agente.name):
                runs = (await session.execute(
                    select(Run)
                    .where(Run.agent_id == agente.id)
                    .where(Run.procedure == mem.name)
                    .where(Run.status == "completed")
                    .order_by(Run.id)
                )).scalars().all()
                fila = {
                    "agent": agente.name,
                    "name": mem.name,
                    "description": mem.description,
                    "created_at": mem.created_at,
                    "applied_runs": len(runs),
                    # Sin muestra suficiente no se afirma nada. Un método
                    # recién compilado no tiene curva, tiene un punto.
                    "trend": None,
                }
                if len(runs) >= 6:
                    antes, ahora = _tramo(runs, True), _tramo(runs, False)
                    baseline = antes["tokens"] or 0.0
                    fila["trend"] = {
                        "first": antes,
                        "recent": ahora,
                        "tokens_delta_pct": (
                            round((ahora["tokens"] - baseline) / baseline * 100, 1)
                            if baseline else None
                        ),
                    }
                salida.append(fila)
    salida.sort(key=lambda f: (-f["applied_runs"], f["name"]))
    return salida
