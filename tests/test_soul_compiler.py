"""Soul-4 — el eslabón que convierte System 2 en System 1.

La tesis del producto: resolver algo deliberando no deja como resultado la
respuesta, deja el MÉTODO. La próxima vez no se vuelve a derivar, se aplica.

Antes de esto Rugol tenía las dos mitades sueltas y ningún puente. Medido en el
código: `classify()` recibía el prompt y el nombre del agente, nada más. Un
pedido resuelto cincuenta veces se clasificaba S2 la vez cincuenta y uno,
idéntico a la primera — el sistema podía volverse más sabio, nunca más rápido.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from core.memory.store import (
    PROCEDURE_KIND,
    add_memory,
    get_memory,
    list_procedures,
    procedures_catalogue,
)


@pytest.fixture()
def agente(tmp_path, monkeypatch):
    """Un agente con su carpeta de memoria aislada."""
    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    import core.config as config
    config.get_settings.cache_clear()
    return "analista-test"


# ── Un procedimiento es una memoria de otro tipo ─────────────────────────────

def test_a_procedure_is_a_memory_of_its_own_kind(agente):
    add_memory(agente, "un_hecho", "algo que sé", "contenido", kind="project")
    add_memory(
        agente, "cierre_ventas_mensual",
        "Cómo cerrar las ventas de un mes",
        "**Cuándo aplica:** cierre mensual de MX\n\n**Pasos:**\n1. Restar devoluciones",
        kind=PROCEDURE_KIND,
    )
    procs = list_procedures(agente)
    assert [m.name for m in procs] == ["cierre_ventas_mensual"], (
        "un hecho no es un método; mezclarlos hace que el dispatcher crea que "
        "sabe hacer algo porque conoce un dato"
    )


def test_the_memory_tool_accepts_the_new_kind():
    from core.mcp.memory_service import _VALID_KINDS

    assert PROCEDURE_KIND in _VALID_KINDS, (
        "si la tool lo rechaza, el compilador no puede guardar nada"
    )


def test_the_catalogue_gives_the_dispatcher_what_it_needs_and_no_more(agente):
    add_memory(
        agente, "cierre_ventas_mensual", "Cómo cerrar las ventas de un mes",
        "**Pasos:**\n1. paso secreto y largo\n2. otro paso", kind=PROCEDURE_KIND,
    )
    cat = procedures_catalogue(agente)
    assert "cierre_ventas_mensual" in cat
    assert "Cómo cerrar las ventas de un mes" in cat
    assert "paso secreto" not in cat, (
        "el clasificador sólo decide SI hay método; los pasos los lee después "
        "el agente que ejecuta. Mandarlos acá es pagar tokens por nada"
    )


def test_an_agent_with_nothing_compiled_sends_no_catalogue(agente):
    assert procedures_catalogue(agente) == ""


# ── El dispatcher puede degradar a s1 por un método ──────────────────────────

def test_the_classifier_can_name_a_procedure():
    from core.soul.dispatcher import _parse_decision

    d = _parse_decision(
        '{"track":"s1","confidence":0.9,"rationale":"ya tiene método",'
        '"procedure":"cierre_ventas_mensual"}'
    )
    assert d.track == "s1"
    assert d.procedure == "cierre_ventas_mensual"


def test_a_decision_without_a_procedure_carries_none():
    from core.soul.dispatcher import _parse_decision

    assert _parse_decision('{"track":"s2","confidence":0.7,"rationale":"x"}').procedure is None


def test_classify_accepts_the_catalogue():
    from core.soul.dispatcher import classify

    assert "procedures" in inspect.signature(classify).parameters, (
        "sin esto el clasificador nunca se entera de lo que el agente aprendió, "
        "que era exactamente el bug"
    )


def test_the_classifier_prompt_tells_it_what_a_procedure_is():
    from core.soul.dispatcher import _CLASSIFIER_SYSTEM_PROMPT

    assert "COMPILED PROCEDURES" in _CLASSIFIER_SYSTEM_PROMPT
    assert "Never invent a name" in _CLASSIFIER_SYSTEM_PROMPT, (
        "un modelo chico inventa nombres plausibles; hay que decírselo"
    )


# ── Los tres filtros antes de aplicar un método ──────────────────────────────
# Enrutar a un modelo barato SIN darle el método es peor que no haber enrutado.

class _D:
    def __init__(self, track="s1", confidence=0.95, procedure=None, bypassed=False):
        self.track, self.confidence, self.procedure, self.bypassed = (
            track, confidence, procedure, bypassed
        )


def _orq():
    from pathlib import Path

    from core.runner.orchestrator import RuntimeOrchestrator

    return RuntimeOrchestrator(max_concurrent=1, workspace_dir=Path("."))


def test_an_invented_procedure_name_is_refused(agente):
    """El nombre tiene que existir de verdad en la memoria del agente."""
    r = _orq()._resolve_procedure(agente, _D(procedure="metodo_que_no_existe"))
    assert r is None


def test_a_procedure_below_the_confidence_floor_is_refused(agente):
    add_memory(agente, "m", "Cómo hacer algo", "pasos", kind=PROCEDURE_KIND)
    assert _orq()._resolve_procedure(agente, _D(procedure="m", confidence=0.4)) is None


def test_a_procedure_on_an_s2_decision_is_refused(agente):
    """Si el clasificador igual decidió deliberar, no se aplica atajo."""
    add_memory(agente, "m", "Cómo hacer algo", "pasos", kind=PROCEDURE_KIND)
    assert _orq()._resolve_procedure(agente, _D(track="s2", procedure="m")) is None


def test_a_real_procedure_with_confidence_is_applied(agente):
    add_memory(agente, "cierre_ventas_mensual", "Cómo cerrar ventas", "pasos", kind=PROCEDURE_KIND)
    r = _orq()._resolve_procedure(agente, _D(procedure="cierre_ventas_mensual"))
    assert r is not None and r.name == "cierre_ventas_mensual"


def test_the_method_is_injected_outside_the_memory_budget():
    """El bloque de memoria corta por presupuesto. El método elegido no puede
    caerse por ese corte: sería mandar a un modelo barato un trabajo sin el
    método que justificaba mandárselo."""
    import core.runner.orchestrator as orch

    src = inspect.getsource(orch.RuntimeOrchestrator.enqueue)
    assert "build_procedure_block" in src
    i_mem = src.index("build_memory_block")
    i_proc = src.index("procedimiento is not None")
    assert i_proc > i_mem, "el método se antepone DESPUÉS de componer la memoria"


# ── El compilador sólo corre cuando hubo deliberación ────────────────────────

def test_the_compiler_only_fires_after_a_deliberate_run():
    import core.runner.orchestrator as orch

    src = inspect.getsource(orch.RuntimeOrchestrator._maybe_spawn_compiler)
    assert 'track != "s2"' in src, (
        "sin deliberación no hay método que extraer, y preguntarlo igual es "
        "pagar un Haiku por corrida para que conteste que no hay nada"
    )


def test_the_compiler_does_not_compile_itself():
    import core.runner.orchestrator as orch

    src = inspect.getsource(orch.RuntimeOrchestrator._maybe_spawn_compiler)
    assert "-compiler" in src and "-checkpoint" in src


def test_the_compiler_prompt_separates_method_from_result():
    from core.soul.compiler import _COMPILER_PROMPT

    assert "No te interesa el RESULTADO" in _COMPILER_PROMPT
    assert "Ante la duda" in _COMPILER_PROMPT, (
        "un procedimiento vago es peor que ninguno: el dispatcher lo toma por "
        "bueno y degrada una tarea que había que pensar"
    )


def test_the_compiler_can_be_turned_off():
    from core.config import get_settings

    assert hasattr(get_settings(), "SOUL_COMPILE_PROCEDURES_ENABLED")


# ── La medición: sin esto la tesis no es falsable ────────────────────────────

def test_a_run_records_which_method_it_applied():
    from core.db.models import Run

    assert hasattr(Run, "procedure"), (
        "sin esta columna no se puede agrupar por método, y 'el agente se "
        "vuelve más rápido' queda como una afirmación que nadie puede refutar"
    )


def test_the_trend_needs_a_real_sample():
    """Una corrida rápida por suerte no es una tendencia."""
    import core.api.procedures as api

    src = inspect.getsource(api.list_procedures_with_evidence)
    assert "len(runs) >= 6" in src
    assert '"trend": None' in src, "sin muestra, se devuelve None, no un número inventado"


def test_the_new_column_is_registered_in_the_migrator():
    """Agregar la columna al modelo no la agrega a una base que ya existe.

    Medido en vivo: el endpoint devolvía 500 con `no such column:
    runs.procedure` sobre la instalación de ensayo, porque el modelo la tenía
    y el migrador no. Los tests pasaban igual: crean la base desde cero.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "core/db/base.py").read_text(encoding="utf-8")
    assert '("runs", "procedure"' in src


def test_the_injected_method_uses_the_real_field(agente):
    """`Memory` guarda el texto en `.body`, no en `.content`.

    Medido en vivo: la corrida devolvía 500 con `'Memory' object has no
    attribute 'content'`. Los tests de arriba no lo agarraron porque verifican
    el código fuente, no lo ejecutan con una memoria de verdad.
    """
    add_memory(agente, "m", "Cómo hacer algo", "los pasos", kind=PROCEDURE_KIND)
    mem = get_memory(agente, "m")
    assert mem is not None
    assert mem.body.strip() == "los pasos"
    assert not hasattr(mem, "content")


def test_the_method_block_tells_the_agent_to_apply_and_to_object(agente):
    """Las dos instrucciones son igual de necesarias.

    Sin "aplicá esto": el agente re-deriva el método, gasta lo mismo que la
    primera vez, y el dispatcher lo mandó a un modelo más chico para nada.

    Sin "si no calza, decilo": un método forzado sobre un pedido que no le
    corresponde es peor que no tenerlo, y el clasificador se equivoca a veces.
    """
    from core.runner.orchestrator import build_procedure_block

    add_memory(agente, "cierre_ventas", "Cómo cerrar ventas", "1. restar devoluciones", kind=PROCEDURE_KIND)
    bloque = build_procedure_block(get_memory(agente, "cierre_ventas"))

    assert "cierre_ventas" in bloque
    assert "restar devoluciones" in bloque, "el método tiene que ir ENTERO, no su título"
    assert "en vez de" in bloque and "derivarlo" in bloque
    assert "NO" in bloque and "decilo" in bloque


# ── Extinción: lo que no funciona deja de ofrecerse ──────────────────────────
# Soul-4 sin freno acumula métodos mediocres, y un catálogo lleno de métodos
# vagos es PEOR que uno vacío: el dispatcher los toma por buenos y manda a un
# modelo barato trabajo que había que pensar.

@pytest.mark.asyncio
async def test_a_method_that_keeps_failing_stops_being_offered(agente, monkeypatch):
    from core.soul import procedures as procs

    add_memory(agente, "malo", "Cómo hacer algo mal", "pasos", kind=PROCEDURE_KIND)
    add_memory(agente, "bueno", "Cómo hacer algo bien", "pasos", kind=PROCEDURE_KIND)

    async def historial(_):
        return {"malo": (6, 5), "bueno": (6, 1)}

    monkeypatch.setattr(procs, "_track_record", historial)
    cat = await procs.catalogue_for(agente)
    assert "bueno" in cat
    assert "malo" not in cat


@pytest.mark.asyncio
async def test_a_new_method_gets_to_fail_once_without_dying(agente, monkeypatch):
    """Sin umbral de muestra, lo único que sobrevive es lo que tuvo suerte."""
    from core.soul import procedures as procs

    add_memory(agente, "nuevo", "Cómo hacer algo", "pasos", kind=PROCEDURE_KIND)

    async def historial(_):
        return {"nuevo": (1, 1)}  # 100% de fallo, pero UNA sola aplicación

    monkeypatch.setattr(procs, "_track_record", historial)
    assert "nuevo" in await procs.catalogue_for(agente)


@pytest.mark.asyncio
async def test_the_most_used_method_goes_first(agente, monkeypatch):
    """Cuando hay que recortar, se cae lo que nadie usa — no lo alfabético."""
    from core.soul import procedures as procs

    add_memory(agente, "a_poco_usado", "Cómo A", "p", kind=PROCEDURE_KIND)
    add_memory(agente, "z_muy_usado", "Cómo Z", "p", kind=PROCEDURE_KIND)

    async def historial(_):
        return {"a_poco_usado": (1, 0), "z_muy_usado": (30, 0)}

    monkeypatch.setattr(procs, "_track_record", historial)
    cat = await procs.catalogue_for(agente)
    assert cat.index("z_muy_usado") < cat.index("a_poco_usado")


@pytest.mark.asyncio
async def test_a_broken_query_offers_everything_instead_of_nothing(agente, monkeypatch):
    """Quedarse sin métodos por un problema de base sería perder la capacidad
    entera por un rasguño."""
    from core.soul import procedures as procs

    add_memory(agente, "m", "Cómo hacer algo", "pasos", kind=PROCEDURE_KIND)

    async def explota(_):
        raise RuntimeError("base caída")

    monkeypatch.setattr(procs, "_track_record", explota)
    assert "m" in await procs.catalogue_for(agente)


@pytest.mark.asyncio
async def test_retiring_never_deletes_the_memory(agente, monkeypatch):
    """Borrar memoria de un agente por una estadística es irreversible, y la
    estadística puede estar midiendo otra cosa."""
    from core.soul import procedures as procs

    add_memory(agente, "malo", "Cómo hacer algo mal", "pasos", kind=PROCEDURE_KIND)

    async def historial(_):
        return {"malo": (10, 9)}

    monkeypatch.setattr(procs, "_track_record", historial)
    await procs.catalogue_for(agente)
    assert get_memory(agente, "malo") is not None, "retirar es dejar de ofrecer, no borrar"


@pytest.mark.asyncio
async def test_the_catalogue_has_a_ceiling(agente, monkeypatch):
    """Con cuarenta opciones, 'el que más se parece' deja de significar algo."""
    from core.soul import procedures as procs

    for i in range(procs._TOPE + 10):
        add_memory(agente, f"m{i:03d}", f"Cómo {i}", "p", kind=PROCEDURE_KIND)

    async def historial(_):
        return {}

    monkeypatch.setattr(procs, "_track_record", historial)
    cat = await procs.catalogue_for(agente)
    assert len(cat.splitlines()) == procs._TOPE


def test_the_orchestrator_uses_the_filtered_catalogue():
    import inspect

    from core.runner.orchestrator import RuntimeOrchestrator

    src = inspect.getsource(RuntimeOrchestrator.enqueue)
    assert "catalogue_for" in src, (
        "sin el filtro, un método que viene fallando se sigue ofreciendo para siempre"
    )


@pytest.mark.asyncio
async def test_at_the_ceiling_the_compiler_is_told_to_replace(agente, monkeypatch):
    """Agregar el método número 21 no mejora nada: empeora la decisión del
    dispatcher, que con demasiadas opciones deja de distinguir."""
    from core.soul import compiler, procedures

    for i in range(procedures._TOPE):
        add_memory(agente, f"m{i:03d}", f"Cómo {i}", "p", kind=PROCEDURE_KIND)

    capturado = {}

    async def falso_run(**kw):
        capturado["prompt"] = kw["prompt"]
        class R:
            final_text = compiler.NO_PROCEDURE
            cost_usd = 0.0
            input_tokens = output_tokens = 0
        return R()

    import core.runner.claude_runner as cr
    monkeypatch.setattr(cr, "run_agent", falso_run)
    await compiler.run_compiler(
        agent_name=agente, user_prompt="x", agent_response="y",
        workspace_dir=Path("."),
    )
    assert "REEMPLAZAR" in capturado["prompt"]
    assert "forget_memory" in capturado["prompt"]


@pytest.mark.asyncio
async def test_below_the_ceiling_there_is_no_pressure_to_replace(agente, monkeypatch):
    from core.soul import compiler

    add_memory(agente, "uno", "Cómo uno", "p", kind=PROCEDURE_KIND)
    capturado = {}

    async def falso_run(**kw):
        capturado["prompt"] = kw["prompt"]
        class R:
            final_text = compiler.NO_PROCEDURE
            cost_usd = 0.0
            input_tokens = output_tokens = 0
        return R()

    import core.runner.claude_runner as cr
    monkeypatch.setattr(cr, "run_agent", falso_run)
    await compiler.run_compiler(
        agent_name=agente, user_prompt="x", agent_response="y",
        workspace_dir=Path("."),
    )
    assert "REEMPLAZAR" not in capturado["prompt"]
    assert "Ya tenés 1" in capturado["prompt"]
