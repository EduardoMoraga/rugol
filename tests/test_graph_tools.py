"""El grafo compartido — la promesa que la página hacía y nadie cumplía.

La vista de Ontología decía "Agents will populate this as they learn". Ningún
agente tenía forma de escribir un hecho: los únicos caminos eran las semillas
del arquitecto y un POST a mano. La página estaba vacía y iba a seguir vacía
para siempre.

Ahora el grafo es herramienta de los dos motores, por el mismo servicio MCP que
la memoria. Y la asimetría es el diseño: la libreta es privada de cada agente,
el grafo es común.
"""
from __future__ import annotations

import pytest

from core.db import init_db
from core.mcp.memory_service import MCP_SERVER_NAME, TOOLS, call_tool_async


def _texto(resultado: dict) -> str:
    return resultado["content"][0]["text"]


@pytest.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/graph.db")
    import core.db as dbmod
    dbmod._engine = None
    dbmod._session_factory = None
    await init_db()
    yield
    dbmod._engine = None
    dbmod._session_factory = None


def test_the_graph_tools_are_actually_exposed():
    """Sin esto el modelo nunca las ve, y la página sigue vacía."""
    nombres = {t["name"] for t in TOOLS}
    assert "remember_fact" in nombres
    assert "recall_facts" in nombres


def test_the_prompt_names_tools_that_exist():
    """Las reglas decían `mcp__rugol-soul__…` — un servidor que ya no existe.

    El prompt nombraba herramientas ausentes y sólo la adivinanza del modelo
    tapaba el hueco.
    """
    from core.soul.auto_memory import AUTO_MEMORY_RULES

    assert "rugol-soul" not in AUTO_MEMORY_RULES
    assert f"mcp__{MCP_SERVER_NAME}__save_memory" in AUTO_MEMORY_RULES
    for t in TOOLS:
        assert t["name"] in AUTO_MEMORY_RULES, (
            f"la herramienta {t['name']} existe pero el agente no sabe que existe"
        )


@pytest.mark.asyncio
async def test_an_agent_can_write_a_fact_and_read_it_back(db):
    escrito = await call_tool_async("analista", "remember_fact", {
        "subject": "Philips", "relation": "es_cliente_de", "object": "Increxa",
    })
    assert escrito["isError"] is False
    leido = _texto(await call_tool_async("analista", "recall_facts", {"about": "Philips"}))
    assert "Philips → es_cliente_de → Increxa" in leido


@pytest.mark.asyncio
async def test_what_one_agent_learns_another_can_read(db):
    """El punto entero del grafo. Si no cruza, no es compartido."""
    await call_tool_async("scout", "remember_fact", {
        "subject": "Versuni", "relation": "usa", "object": "Power BI",
    })
    leido = _texto(await call_tool_async("otro-agente", "recall_facts", {"about": "Versuni"}))
    assert "Power BI" in leido


@pytest.mark.asyncio
async def test_private_memories_do_not_cross(db, tmp_path):
    """Y la libreta personal sigue siendo personal. La asimetría es el diseño."""
    await call_tool_async("agente-a", "save_memory", {
        "name": "secreto-de-a", "description": "sólo de A", "content": "algo", "kind": "note",
    })
    mias = _texto(await call_tool_async("agente-b", "list_my_memories", {}))
    assert "secreto-de-a" not in mias


@pytest.mark.asyncio
async def test_restating_a_fact_does_not_duplicate_it(db):
    """Un agente que reafirma lo mismo en cada corrida haría el grafo ilegible."""
    from core.ontology.store import get_ontology

    for _ in range(5):
        await call_tool_async("terco", "remember_fact", {
            "subject": "OPPO", "relation": "es_cliente_de", "object": "Increxa",
        })
    triples = await get_ontology().around("OPPO")
    assert len(triples) == 1, f"cinco veces el mismo hecho dejó {len(triples)} aristas"


@pytest.mark.asyncio
async def test_recall_looks_in_both_directions(db):
    """Preguntar por "Increxa" tiene que traer los hechos donde es el objeto.

    Mirar sólo las salientes dejaba la mitad del conocimiento invisible.
    """
    await call_tool_async("a", "remember_fact", {
        "subject": "Hisense", "relation": "es_cliente_de", "object": "Increxa",
    })
    leido = _texto(await call_tool_async("a", "recall_facts", {"about": "Increxa"}))
    assert "Hisense" in leido


@pytest.mark.asyncio
async def test_recall_by_free_text(db):
    await call_tool_async("a", "remember_fact", {
        "subject": "reporte_semanal", "relation": "pertenece_a", "object": "DiDi MX",
    })
    leido = _texto(await call_tool_async("a", "recall_facts", {"query": "didi"}))
    assert "reporte_semanal" in leido, "la búsqueda debe ser insensible a mayúsculas"


@pytest.mark.asyncio
async def test_an_empty_graph_answers_instead_of_failing(db):
    r = await call_tool_async("a", "recall_facts", {"about": "NadaQueVer"})
    assert r["isError"] is False
    assert "nothing recorded" in _texto(r)


@pytest.mark.asyncio
async def test_incomplete_facts_are_rejected_with_a_reason(db):
    r = await call_tool_async("a", "remember_fact", {"subject": "X", "relation": ""})
    assert r["isError"] is True
    assert "relation" in _texto(r)

    r = await call_tool_async("a", "recall_facts", {})
    assert r["isError"] is True
    assert "about" in _texto(r) and "query" in _texto(r)


@pytest.mark.asyncio
async def test_a_broken_graph_does_not_kill_the_run(db, monkeypatch):
    """Una herramienta que levanta corta la corrida entera. Devolver el error
    como resultado deja al modelo corregir y seguir."""
    class Roto:
        async def add_edge(self, *a, **k):
            raise RuntimeError("la base explotó")

    monkeypatch.setattr("core.ontology.store.get_ontology", lambda: Roto())
    r = await call_tool_async("a", "remember_fact", {
        "subject": "A", "relation": "b", "object": "C",
    })
    assert r["isError"] is True
    assert "la base explotó" in _texto(r)


# ── El motor por corrida, desde la API ───────────────────────────────────────
# Pedir `{"engine": "codex"}` a POST /api/agents/{id}/run se descartaba en
# silencio y la corrida salía en Claude. Telegram podía elegir con /motor; la
# API no, así que ni el dashboard ni un script podían. Y un campo ignorado en
# silencio es peor que un error: creés que probaste el otro motor y no.

def test_the_run_api_accepts_an_engine():
    from core.api.agents import RunNowBody

    assert "engine" in RunNowBody.model_fields


def test_an_unknown_field_is_rejected_instead_of_ignored():
    """La causa real del silencio: Pydantic descartaba lo que no conocía."""
    from pydantic import ValidationError

    from core.api.agents import RunNowBody

    with pytest.raises(ValidationError):
        RunNowBody(prompt="hola", motor="codex")  # typo plausible


def test_switching_engines_drops_the_session():
    """Un session_id pertenece al CLI que lo creó.

    Pasarlo al otro motor da "no rollout found" y la corrida muere por una razón
    que no tiene nada que ver con lo que pediste.
    """
    import inspect

    from core.api.agents import run_now

    fuente = inspect.getsource(run_now)
    assert "session_id = None if engine_override != agent_engine" in fuente


def test_an_unknown_engine_is_an_error_not_a_silent_substitution():
    """`normalize_engine` convierte "gemini" en "claude" a propósito.

    Por eso validar comparando su SALIDA contra ENGINES nunca falla: pedías
    gemini, corría Claude, y el 400 no salía nunca. Medido en vivo: devolvía 202.
    """
    from core.runner.base import is_known_engine, normalize_engine

    assert normalize_engine("gemini") == "claude"  # el comportamiento permisivo sigue
    assert is_known_engine("gemini") is False      # pero la API ya no lo acepta
    assert is_known_engine("codex") is True
    assert is_known_engine("gpt") is True          # los alias siguen valiendo
    assert is_known_engine("") is False
    assert is_known_engine(None) is False
