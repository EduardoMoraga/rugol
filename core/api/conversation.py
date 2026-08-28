"""La conversación del dashboard, que hasta ahora no existía en ningún lado.

El chat de la ficha del agente guardaba sus turnos en el estado de React y el
`session_id` con ellos. Recargar la página no era "perder el scroll": era
**empezar de cero**. El agente olvidaba el hilo, no sólo la pantalla.

Y lo llamativo es que Telegram no tenía ese problema: desde v0.6 persiste su
sesión en `chat_sessions` y sobrevive incluso a reiniciar el backend. O sea que
la puerta principal del producto era peor que la de mensajería en lo único que
un chat tiene que hacer bien.

Acá no hay tabla nueva. El hilo ya estaba escrito en dos lugares que existían:

- El `session_id` va al mismo `session_store` que usa Telegram, con
  `channel_type="dashboard"`. Una implementación, no dos.
- Los turnos SON las corridas: `Run.prompt` y `Run.final_text` con ese
  `session_id`. No hace falta guardar los mensajes otra vez.

Esto además es el cimiento de lo que viene. Un "canal" con varios agentes
adentro es un hilo que sobrevive a la pestaña; sin eso, no hay canal que valga.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from core.adapters import session_store
from core.db import async_session_factory
from core.db.models import Agent, Run

router = APIRouter(prefix="/agents", tags=["agents"])

CHANNEL = "dashboard"
# Cuántos turnos se devuelven al rehidratar. Una conversación larga no tiene
# por qué viajar entera cada vez que alguien abre la pestaña.
_MAX_TURNOS = 40


async def _agent_or_404(agent_id: int) -> Agent:
    async with async_session_factory() as session:
        agent = await session.get(Agent, agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        return agent


@router.get("/{agent_id}/conversation")
async def get_conversation(agent_id: int) -> dict:
    """El hilo vivo de este agente en el dashboard: sesión + turnos.

    Devuelve `session_id: null` y lista vacía cuando no hay conversación
    abierta — que es el estado normal la primera vez, no un error.
    """
    agent = await _agent_or_404(agent_id)
    sesiones = await session_store.load_all(CHANNEL)
    session_id = sesiones.get(agent.name)
    if not session_id:
        return {"session_id": None, "turns": []}

    async with async_session_factory() as session:
        runs = (await session.execute(
            select(Run)
            .where(Run.agent_id == agent_id)
            .where(Run.session_id == session_id)
            # Las corridas sintéticas —checkpoint, compilador, abogado del
            # diablo— no son turnos de la conversación. Mostrarlas sería
            # enseñarle al usuario el trabajo interno como si le hablara.
            .where(Run.source == CHANNEL)
            .order_by(Run.id)
            .limit(_MAX_TURNOS)
        )).scalars().all()

    return {
        "session_id": session_id,
        "turns": [
            {
                "run_id": r.id,
                "prompt": r.prompt,
                "final_text": r.final_text or "",
                "status": r.status,
                "track": r.track,
                "procedure": r.procedure,
                "outcome": r.outcome,
                "engine": r.engine or "claude",
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in runs
        ],
    }


@router.post("/{agent_id}/conversation/reset")
async def reset_conversation(agent_id: int) -> dict:
    """Cierra el hilo. El siguiente mensaje arranca de cero.

    Mismo gesto que `/reset` en Telegram, y por el mismo motivo: a veces la
    conversación se contaminó y arrastrarla cuesta más de lo que aporta. Las
    corridas viejas NO se borran — siguen en el historial y en la medición; lo
    único que se corta es el hilo.
    """
    agent = await _agent_or_404(agent_id)
    habia = await session_store.delete_one(CHANNEL, agent.name)
    return {"agent": agent.name, "had_session": habia}
