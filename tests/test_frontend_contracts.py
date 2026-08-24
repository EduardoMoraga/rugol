"""Contratos entre el backend y el frontend que ningún test de Python tocaba.

Los dos son sobre lo mismo: el backend agrega un estado o un tópico, el frontend
no se enteró, y el resultado es una pantalla que miente sin que nada falle.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
API_TS = REPO / "dashboard/src/lib/api.ts"
ANT_FARM = REPO / "dashboard/src/components/ant-farm/ant-farm-canvas.tsx"


def _terminal_del_frontend() -> set[str]:
    texto = API_TS.read_text(encoding="utf-8")
    bloque = re.search(
        r"export const TERMINAL_RUN_STATUSES = \[(.*?)\] as const;", texto, re.S
    )
    assert bloque, "no encontré TERMINAL_RUN_STATUSES en el cliente"
    return set(re.findall(r'"([a-z]+)"', bloque.group(1)))


def test_both_sides_agree_on_which_runs_are_over():
    from core.db.models import TERMINAL_RUN_STATUSES as backend

    assert _terminal_del_frontend() == set(backend), (
        "el backend y el dashboard no coinciden en qué corridas terminaron: "
        "el chat se queda refrescando para siempre una que nunca va a cambiar"
    )


def test_the_ant_farm_turns_the_ant_off_on_every_terminal_status():
    """Escuchaba sólo `completed` y `failed`.

    Una corrida cancelada dejaba el override en "running" —y el override le gana
    al valor de la base— así que la hormiga seguía corriendo en pantalla para
    siempre.
    """
    fuente = ANT_FARM.read_text(encoding="utf-8")
    assert "isTerminalRunStatus" in fuente, (
        "el ant-farm volvió a enumerar estados a mano: el próximo estado nuevo "
        "deja hormigas corriendo para siempre"
    )
    assert 'e.topic === "run:completed"' not in fuente
    assert 'e.topic === "run:failed"' not in fuente


def test_every_terminal_status_has_a_bus_topic_the_frontend_can_hear():
    """El frontend escucha `run:*` y corta el sufijo. Si el backend publicara un
    estado terminal con otro nombre de tópico, la hormiga no se apagaría."""
    import inspect

    from core.runner import orchestrator

    fuente = inspect.getsource(orchestrator)
    assert 'publish(f"run:{status}"' in fuente, (
        "el tópico tiene que derivarse del estado: si se escriben a mano, "
        "agregar un estado deja al frontend sordo"
    )
