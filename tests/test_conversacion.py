"""El hilo del dashboard, que hasta ahora no existía en ningún lado.

El chat de la ficha del agente guardaba los turnos y el `session_id` en el
estado de React. Recargar la página no perdía el scroll: perdía la
CONVERSACIÓN. El agente empezaba de cero y nada lo decía.

Lo llamativo es que Telegram no tenía ese problema —persiste su sesión desde
v0.6— así que la puerta principal del producto era peor que la de mensajería en
lo único que un chat tiene que hacer bien.
"""
from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHAT = REPO / "dashboard/src/components/agents/agent-chat.tsx"


def test_the_thread_survives_a_reload():
    from core.main import app

    rutas = [r.path for r in app.routes if getattr(r, "methods", None)]
    assert "/api/agents/{agent_id}/conversation" in rutas
    assert "/api/agents/{agent_id}/conversation/reset" in rutas


def test_it_reuses_the_store_telegram_already_had():
    """Dos implementaciones de 'la sesión de un chat' están condenadas a
    separarse. Telegram ya tenía una que funciona."""
    import core.api.conversation as conv

    src = inspect.getsource(conv)
    assert "session_store" in src
    assert "ChatSession" not in src, "no hace falta tabla nueva: el hilo ya estaba escrito"


def test_the_turns_are_the_runs_not_a_second_copy():
    """Guardar los mensajes otra vez sería una segunda fuente de verdad que se
    desincroniza con la primera."""
    import core.api.conversation as conv

    src = inspect.getsource(conv.get_conversation)
    assert "Run.session_id == session_id" in src
    assert "r.prompt" in src and "r.final_text" in src


def test_internal_runs_are_not_shown_as_turns():
    """El checkpoint, el compilador y el abogado del diablo son trabajo
    interno. Mostrarlos sería enseñarle al usuario el motor como si le
    estuviera hablando."""
    import core.api.conversation as conv

    src = inspect.getsource(conv.get_conversation)
    assert "Run.source == CHANNEL" in src


def test_no_conversation_is_not_an_error():
    """Es el estado normal la primera vez."""
    import core.api.conversation as conv

    src = inspect.getsource(conv.get_conversation)
    assert '"session_id": None, "turns": []' in src


def test_reset_cuts_the_thread_without_deleting_history():
    """Las corridas viejas siguen en el historial y en la medición. Lo único
    que se corta es el hilo."""
    import core.api.conversation as conv

    src = inspect.getsource(conv.reset_conversation)
    assert "delete_one" in src
    assert "Run" not in src, "resetear no puede borrar corridas"


def test_the_backend_persists_the_dashboard_session():
    from core.runner.orchestrator import RuntimeOrchestrator

    src = inspect.getsource(RuntimeOrchestrator)
    assert 'session_store.save("dashboard"' in src


# ── El frontend ──────────────────────────────────────────────────────────────

def test_the_chat_rehydrates_from_the_backend():
    src = CHAT.read_text(encoding="utf-8")
    assert "fetchConversation" in src


def test_it_rehydrates_once_and_never_over_a_live_turn():
    """Llegar tarde y pisar un turno en vuelo sería peor que no rehidratar."""
    src = CHAT.read_text(encoding="utf-8")
    assert "hydratedRef" in src
    assert "if (turns.length > 0" in src


def test_the_session_survives_even_with_an_empty_screen():
    """Si la pantalla está vacía pero el backend recuerda el hilo, el próximo
    mensaje tiene que continuarlo — no abrir uno nuevo."""
    src = CHAT.read_text(encoding="utf-8")
    assert "persisted.data?.session_id ?? null" in src


def test_a_rehydrated_turn_keeps_its_real_status():
    """Un turno que falló hace meses tiene que verse como falló."""
    src = CHAT.read_text(encoding="utf-8")
    assert "isTerminalRunStatus(tr.status)" in src
