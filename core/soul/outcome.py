"""¿La tarea salió bien? — distinto de que el proceso haya terminado.

Rugol equiparaba dos cosas que no son la misma:

    "la ejecución terminó técnicamente"  ≠  "el procedimiento funcionó"

Una corrida puede quedar `completed` con una respuesta equivocada, un análisis
mediocre, o una conclusión correcta por casualidad. Mientras la extinción de
métodos mirara sólo `status`, un método malo que siempre produce texto sobrevivía
para siempre. Es la brecha exacta entre acumular memoria y madurar.

Este módulo junta veredictos, con una regla que atraviesa todo: **el silencio no
es un veredicto**. Casi todas las corridas no van a tener outcome, y eso está
bien. Inventar señal donde no la hay sería peor que no medir: convertiría el
instrumento en ruido con aspecto de dato.

Tres fuentes, de la más fuerte a la más débil:

**`check`** — una verificación objetiva: los tests pasan, el archivo que tenía
que existir existe. Es la única que no depende de interpretar a nadie. Hoy la
declara quien llama; el gancho está puesto para cuando un proyecto pueda
declarar su propio contrato.

**`user`** — la persona dijo que estaba mal, o que estaba bien. Es el veredicto
más valioso y el más escaso: nadie califica sus conversaciones.

**`redo`** — volvió a pedir lo mismo enseguida. Es señal indirecta y por eso
sólo cuenta como `bad` cuando es inequívoca: mismo agente, ventana corta, y un
pedido que se parece mucho al anterior. Reformular una pregunta a los diez
segundos casi siempre significa que la respuesta no sirvió. A los diez minutos
ya no significa nada.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from sqlalchemy import desc, select

from core.db import async_session_factory
from core.db.models import Run

logger = logging.getLogger(__name__)

GOOD, BAD = "good", "bad"

# Un veredicto ARRANCA el mensaje, con a lo sumo una interjección adelante
# ("Uf, está mal"). Con una ventana más ancha se colaba el contenido: medido,
# "revisá si el pipeline no funciona bien" se leía como reproche porque la
# frase caía en el carácter 21. Un pedido empieza con un verbo; una reacción,
# con el juicio.
_INICIO_MAXIMO = 12

# Ventana dentro de la cual repetir un pedido se lee como "no me sirvió". Más
# allá, la gente simplemente vuelve a un tema.
_VENTANA_REDO = dt.timedelta(minutes=3)
# Cuánto se tienen que parecer dos pedidos para considerarlos el mismo.
_PARECIDO_MINIMO = 0.6

# Frases con las que alguien dice, sin ambigüedad, que algo salió mal o bien.
# Deliberadamente cortas y explícitas: la duda se resuelve NO marcando nada.
# `de nuevo` / `otra vez` NO están acá a propósito: "hacelo de nuevo pero con
# agosto" es un pedido legítimo, no un reproche. La repetición la detecta la
# heurística `redo`, que además exige que el pedido se PAREZCA al anterior.
_MALO = re.compile(
    r"\b(no es (eso|lo que|así)|está mal|esta mal|incorrecto|te equivocas(te)?|"
    r"nada que ver|no sirve|no funciona|mal hecho)\b",
    re.IGNORECASE,
)
_BUENO = re.compile(
    r"\b(perfecto|excelente|exacto|justo eso|era eso|quedó|quedo bien|"
    r"gracias,? (buen|perfecto)|funcion[óo])\b",
    re.IGNORECASE,
)


def _tokens(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-záéíóúñ0-9]{4,}", (texto or "").lower())}


def _parecido(a: str, b: str) -> float:
    """Jaccard sobre palabras largas. Suficiente para "¿es el mismo pedido?",
    y no pretende ser más que eso."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def read_verdict(mensaje: str) -> str | None:
    """El veredicto explícito en un mensaje del usuario, o None.

    Un veredicto ARRANCA el mensaje: "está mal, eran las de julio" reacciona a
    lo anterior. "el informe dice que el proceso está mal documentado" es
    contenido, y con una ventana generosa se leía como reproche — medido.

    Por eso no alcanza con que la frase aparezca: tiene que EMPEZAR dentro de
    los primeros caracteres. Ante la duda, None. Marcar de más envenena la
    extinción con juicios que nadie emitió, y un método bueno retirado por un
    falso positivo no deja rastro de por qué desapareció.
    """
    cabeza = (mensaje or "").strip()
    if not cabeza:
        return None
    for patron, veredicto in ((_MALO, BAD), (_BUENO, GOOD)):
        m = patron.search(cabeza)
        if m and m.start() <= _INICIO_MAXIMO:
            return veredicto
    return None


async def note(run_id: int, verdict: str, source: str) -> bool:
    """Anota el veredicto. No pisa uno que ya estaba.

    Lo primero que se dijo vale: si alguien marcó una corrida como mala, una
    heurística posterior no puede blanquearla.
    """
    if verdict not in (GOOD, BAD):
        return False
    try:
        async with async_session_factory() as session:
            fila = await session.get(Run, run_id)
            if fila is None or fila.outcome is not None:
                return False
            fila.outcome = verdict
            fila.outcome_source = source
            await session.commit()
        logger.info("outcome: corrida %s → %s (%s)", run_id, verdict, source)
        return True
    except Exception:
        logger.exception("no pude anotar el outcome de la corrida %s", run_id)
        return False


async def judge_previous(agent_name: str, nuevo_prompt: str) -> None:
    """Con un mensaje nuevo, decide si la corrida anterior salió bien o mal.

    Se llama al ENCOLAR, cuando el mensaje del usuario todavía es una reacción
    a lo anterior. Best-effort de punta a punta: esto nunca puede impedir que
    una corrida arranque.
    """
    try:
        veredicto = read_verdict(nuevo_prompt)
        async with async_session_factory() as session:
            previa = (await session.execute(
                select(Run)
                .join(Run.agent)
                .where(Run.agent.has(name=agent_name))
                .where(Run.status == "completed")
                .where(Run.outcome.is_(None))
                .order_by(desc(Run.id))
                .limit(1)
            )).scalar_one_or_none()
            if previa is None:
                return
            prompt_previo, ended_at, run_id = previa.prompt, previa.ended_at, previa.id

        if veredicto:
            await note(run_id, veredicto, "user")
            return

        # Sin veredicto explícito: ¿volvió a pedir lo mismo enseguida?
        if ended_at is None:
            return
        ahora = dt.datetime.now(dt.UTC)
        if ended_at.tzinfo is None:
            ended_at = ended_at.replace(tzinfo=dt.UTC)
        if ahora - ended_at > _VENTANA_REDO:
            return
        if _parecido(prompt_previo, nuevo_prompt) >= _PARECIDO_MINIMO:
            await note(run_id, BAD, "redo")
    except Exception:
        logger.exception("no pude juzgar la corrida previa de %s", agent_name)
