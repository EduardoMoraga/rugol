"""Soul-4 — Compilación de método: el puente de System 2 a System 1.

La tesis de Rugol, en el ejemplo de Kahneman: 2+2 lo respondes al instante;
710×814 te obliga a deliberar. Pero lo que queda de haber deliberado no es el
número — es la ESTRATEGIA: separar centenas de decenas, multiplicar aparte,
sumar. La próxima vez no vuelves a descubrirla: la aplicas. Ahí un problema que
era System 2 pasa a resolverse casi como System 1.

Rugol ya tenía las dos mitades sueltas:

- El dispatcher (Soul-2) clasifica cada pedido S1 o S2 y enruta a un modelo
  barato o caro.
- El checkpoint (Soul-1.5) extrae HECHOS después de cada corrida ("esta columna
  viene sin descontar devoluciones").

Y le faltaba el eslabón: nada convertía una solución deliberada en un método
reutilizable, y el clasificador no veía nada de lo aprendido. Medido en el
código: `classify()` recibía el prompt y el nombre del agente, punto. Un pedido
resuelto cincuenta veces se clasificaba S2 la vez cincuenta y uno, idéntico a la
primera. El sistema podía volverse más sabio, nunca más rápido.

Este módulo es ese eslabón. Después de una corrida S2 exitosa, pregunta qué
método se usó y, si sirve para una familia de pedidos y no sólo para éste, lo
guarda como una memoria `kind: procedure`. Desde ahí:

  · viaja al prompt como cualquier memoria (no hace falta cañería nueva);
  · el dispatcher lo ve en el catálogo y puede decir "esto ya es S1";
  · la corrida guarda cuál se aplicó, y esa columna es la que permite MEDIR si
    la tesis funciona: misma familia de tarea, menos tokens con el tiempo.

Sin lo último esto sería una linda historia. Con la medición es una afirmación
falsable.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.config import get_settings
from core.llm_models import HAIKU

logger = logging.getLogger(__name__)

# Marca que el compilador devuelve cuando no hay método que valga la pena.
NO_PROCEDURE = "NO_PROCEDURE"


_COMPILER_PROMPT = """Acabás de terminar un run que requirió deliberación (System 2).

Tu tarea ahora NO es resolver nada. Es mirar hacia atrás y decidir si de este
trabajo queda un **método reutilizable**.

## Tu identidad
Eres **{agent_name}**.

## El run que acaba de terminar
**Pedido:**
{user_prompt}

**Lo que respondiste:**
{agent_response}

## La distinción que importa

No te interesa el RESULTADO. Te interesa el CAMINO.

- Resultado: "las ventas de agosto fueron 1.2M". Eso no se guarda: cambia.
- Método: "para cerrar ventas de un mes hay que restar devoluciones primero,
  porque la tabla viene bruta". Eso sí: sirve la próxima vez y la siguiente.

La prueba es esta pregunta: **si mañana llega un pedido parecido pero con otros
datos, ¿esto que escribí me ahorra volver a pensarlo desde cero?** Si la
respuesta es no, no hay método.

## Primero: mirá qué ya compilaste

Llamá `list_my_memories` **antes de guardar nada**. Ya tenés {compilados}
métodos compilados{aviso_tope}.

- Si ya existe un procedimiento para esta familia de pedidos y el de ahora es
  IGUAL: no guardes nada.
- Si ya existe pero esta vez aprendiste un paso que faltaba o una trampa nueva:
  usá `forget_memory` con el viejo y guardá la versión completa. Un método
  mejorado reemplaza al anterior; nunca dejes dos versiones del mismo método.
- Si no existe: seguí.

## Cuándo NO hay método (respondé `{no_procedure}` y terminá)

- El pedido fue único y no pertenece a ninguna familia repetible.
- Lo único que hiciste fue buscar un dato y decirlo.
- El "método" que escribirías es genérico y obvio ("leer el archivo, analizar,
  responder"). Un método que sirve para todo no sirve para nada.
- No estás seguro. Ante la duda, `{no_procedure}`: un procedimiento vago es peor
  que ninguno, porque el dispatcher lo va a tomar por bueno y va a mandar a un
  modelo barato un trabajo que necesitaba pensarse.

## Si SÍ hay método

Llamá `save_memory` UNA vez, con `kind` exactamente `procedure` y este formato
en el `content`:

```
**Cuándo aplica:** <la familia de pedidos que cubre, en una línea concreta>

**Pasos:**
1. <paso>
2. <paso>
3. <paso>

**Ojo con:** <la trampa que descubriste, o dónde falla si te apurás>
```

- `name`: snake_case, nombrá el MÉTODO, no el caso puntual.
  Bien: `cierre_ventas_mensual`. Mal: `ventas_agosto_2026`.
- `description`: una línea que empiece con "Cómo …". Esta línea es la que ve el
  dispatcher para decidir si tu método cubre un pedido nuevo, así que tiene que
  decir para qué sirve, no cómo funciona.

La sección **Cuándo aplica** es la más importante de las tres: es lo que separa
aplicar el método correcto de aplicar uno parecido. Sé concreto — nombrá el
esquema, la carpeta, el tipo de pedido.

Conectá con lo que ya sabés usando wikilinks `[[nombre_de_otra_memoria]]` dentro
del content.

Después de llamar la tool (o de decir `{no_procedure}`), terminá. No le expliques
nada al usuario: esto es trabajo interno.
"""


async def run_compiler(
    *,
    agent_name: str,
    user_prompt: str,
    agent_response: str,
    workspace_dir: Path,
    run_id: int | None = None,
) -> bool:
    """Extrae el método de una corrida deliberada y lo guarda como procedimiento.

    Devuelve True si el compilador llegó a correr (haya guardado o no), False si
    se saltó o falló. Es best-effort de punta a punta: un fallo acá nunca puede
    tocar la respuesta que el usuario ya recibió.

    Corre en Haiku. La evaluación es estructurada y el prompt es fijo, así que
    cuesta fracciones de centavo — y sólo se dispara en corridas S2, que son las
    caras de todos modos.
    """
    settings = get_settings()
    if not settings.SOUL_COMPILE_PROCEDURES_ENABLED:
        return False
    if not (user_prompt or "").strip() or not (agent_response or "").strip():
        return False

    # Import perezoso: el runner importa este módulo por la vía del orquestador.
    from core.mcp.memory_service import claude_server_config, issue_token, revoke_token
    from core.runner.claude_runner import run_agent

    # Cuántos tiene ya. En el tope, agregar uno más no mejora nada: empeora la
    # decisión del dispatcher, que con demasiadas opciones deja de distinguir.
    # Se le dice al modelo para que REEMPLACE en vez de acumular.
    from core.soul.procedures import _TOPE, count_for

    compilados = await count_for(agent_name)
    aviso_tope = (
        f", que es el tope. Si este método vale la pena, tenés que REEMPLAZAR "
        f"uno peor con `forget_memory` — agregar el número {compilados + 1} "
        f"empeora la decisión en vez de mejorarla"
        if compilados >= _TOPE else ""
    )
    prompt = _COMPILER_PROMPT.format(
        agent_name=agent_name,
        user_prompt=(user_prompt or "").strip()[:2000],
        agent_response=(agent_response or "").strip()[:4000],
        no_procedure=NO_PROCEDURE,
        compilados=compilados,
        aviso_tope=aviso_tope,
    )

    # Misma disciplina de identidad que el checkpoint: la CORRIDA se llama
    # "<agente>-compiler" para no contar como corrida del agente ni disparar
    # otro compilador, pero el token se emite con el nombre limpio para que el
    # procedimiento se escriba en el almacén del AGENTE.
    # Foto de los métodos ANTES. El compilador escribe por MCP y el nombre lo
    # elige el modelo, así que la única forma determinista de saber cuál nació
    # es comparar. Parsear el texto de salida sería adivinar.
    from core.memory.store import list_procedures

    antes = {m.name for m in list_procedures(agent_name)}

    memory_token = issue_token(agent_name, run_id=None)
    try:
        result = await run_agent(
            agent_name=f"{agent_name}-compiler",
            prompt=prompt,
            workspace_dir=workspace_dir,
            model=HAIKU,
            tools=None,
            memory_mcp=claude_server_config(memory_token),
        )
    except Exception:
        logger.exception(
            "compilador de %s falló (best-effort, lo trago)", agent_name
        )
        return False
    finally:
        revoke_token(memory_token)

    # Qué método nació de esta corrida. Es el dato que hace honesta la
    # comparación después: esta corrida —la deliberada, la cara— es el ANTES
    # real de ese método, y sin anotarlo quedaba fuera de la medición.
    nacidos = {m.name for m in list_procedures(agent_name)} - antes
    if nacidos and run_id is not None:
        await _stamp_run(run_id, sorted(nacidos)[0])

    text = (result.final_text or "").strip()
    if NO_PROCEDURE in text and "save_memory" not in text:
        logger.info("compilador %s: sin método reutilizable", agent_name)
    else:
        logger.info(
            "compilador %s: método compilado (costo=$%.4f, tokens=%d)",
            agent_name,
            result.cost_usd or 0.0,
            (result.input_tokens or 0) + (result.output_tokens or 0),
        )
    return True


async def _stamp_run(run_id: int, procedure_name: str) -> None:
    """Deja anotado en la corrida qué método produjo.

    Best-effort: si esto falla, el método igual quedó guardado y el agente
    igual lo va a usar. Lo único que se pierde es la línea base de la
    medición, y perder una medición nunca puede costar una capacidad.
    """
    try:
        from core.db import async_session_factory
        from core.db.models import Run

        async with async_session_factory() as session:
            fila = await session.get(Run, run_id)
            if fila is not None:
                fila.compiled_procedure = procedure_name
                await session.commit()
                logger.info(
                    "soul-4: la corrida %s parió el método %r", run_id, procedure_name
                )
    except Exception:
        logger.exception("no pude anotar el método en la corrida %s", run_id)
