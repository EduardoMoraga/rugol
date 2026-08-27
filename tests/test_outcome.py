"""¿La tarea salió bien? — distinto de que el proceso haya terminado.

El hallazgo de una auditoría externa, y tenía razón: Rugol equiparaba
"la ejecución terminó técnicamente" con "el procedimiento funcionó". Mientras
la extinción de métodos mirara sólo `status`, un método incorrecto que siempre
produce texto sobrevivía para siempre.
"""
from __future__ import annotations

import inspect

import pytest

from core.soul.outcome import BAD, GOOD, _parecido, read_verdict

# ── Leer un veredicto sin inventarlo ─────────────────────────────────────────

@pytest.mark.parametrize("mensaje,esperado", [
    ("está mal, eran las de julio", BAD),
    ("No es eso lo que pedí", BAD),
    ("Uf, está mal", BAD),
    ("nada que ver", BAD),
    ("Perfecto, gracias", GOOD),
    ("exacto, así queda", GOOD),
    ("excelente", GOOD),
])
def test_an_explicit_verdict_is_read(mensaje: str, esperado: str):
    assert read_verdict(mensaje) == esperado


@pytest.mark.parametrize("mensaje", [
    # Contenido, no reacción: la frase aparece pero el mensaje es un PEDIDO.
    "el informe dice que el proceso está mal documentado",
    "revisá si el pipeline no funciona bien en produccion",
    "anda a ver por qué el reporte no sirve para nada",
    # Continuaciones normales de una conversación.
    "hacelo de nuevo pero con agosto",
    "y ahora sumá las de agosto",
    "",
    "   ",
])
def test_content_is_not_a_verdict(mensaje: str):
    """Marcar de más envenena la extinción con juicios que nadie emitió, y un
    método bueno retirado por un falso positivo no deja rastro de por qué
    desapareció."""
    assert read_verdict(mensaje) is None


def test_silence_is_not_a_verdict():
    """Casi todas las corridas no van a tener outcome, y está bien. Inventar
    señal donde no la hay convierte el instrumento en ruido con cara de dato."""
    assert read_verdict("dale") is None
    assert read_verdict("ok") is None


# ── Repetir el mismo pedido enseguida ────────────────────────────────────────

def test_the_same_request_looks_the_same():
    a = "dame el cierre de ventas de julio del esquema ventas_mx"
    b = "necesito el cierre de ventas de julio en ventas_mx"
    assert _parecido(a, b) >= 0.5


def test_a_different_request_does_not():
    a = "dame el cierre de ventas de julio"
    b = "diseñá un modelo de atribución multicanal para promociones"
    assert _parecido(a, b) < 0.3


def test_redo_needs_a_short_window():
    """A los diez segundos, reformular significa que no sirvió. A los diez
    minutos, la gente simplemente vuelve a un tema."""
    from core.soul.outcome import _VENTANA_REDO

    assert _VENTANA_REDO.total_seconds() <= 300


# ── El cableado ──────────────────────────────────────────────────────────────

def test_extinction_counts_bad_outcomes_not_just_crashes():
    """El hallazgo de fondo: contar sólo `failed` mide si el proceso reventó,
    no si la tarea salió bien."""
    from core.soul import procedures

    src = inspect.getsource(procedures._track_record)
    assert 'Run.status == "failed"' in src
    assert 'Run.outcome == "bad"' in src, (
        "un método incorrecto que siempre produce texto pasaba por bueno"
    )


def test_the_verdict_is_collected_when_the_next_message_arrives():
    """Es el único momento en que esa señal existe — después se pierde."""
    from core.runner.orchestrator import RuntimeOrchestrator

    src = inspect.getsource(RuntimeOrchestrator.enqueue)
    assert "judge_previous" in src


def test_scheduled_runs_are_not_judged_by_the_next_message():
    """Un cron no reacciona a nada: el mensaje siguiente de una persona no es
    un veredicto sobre lo que disparó el reloj."""
    from core.runner.orchestrator import RuntimeOrchestrator

    src = inspect.getsource(RuntimeOrchestrator.enqueue)
    assert 'req.source in ("telegram", "slack", "dashboard", "api")' in src


def test_the_first_verdict_wins():
    """Si alguien marcó una corrida como mala, una heurística posterior no
    puede blanquearla."""
    from core.soul import outcome

    src = inspect.getsource(outcome.note)
    assert "fila.outcome is not None" in src


def test_a_human_can_state_the_verdict_explicitly():
    from core.main import app

    rutas = [r.path for r in app.routes if getattr(r, "methods", None)]
    assert "/api/runs/{run_id}/outcome" in rutas


def test_the_columns_are_in_the_migrator():
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "core/db/base.py").read_text(encoding="utf-8")
    assert '("runs", "outcome"' in src
    assert '("runs", "outcome_source"' in src
