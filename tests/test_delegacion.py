"""Que un agente pueda pedirle trabajo a otro — y los frenos que lo hacen viable.

Hasta ahora "gugol coordina al equipo" era una descripción, no un mecanismo: las
seis herramientas que Rugol daba a sus agentes eran todas de memoria. Un agente
que dice coordinar y hace todo él solo no coordina, trabaja mucho.

Los tres frenos no son paranoia: son las tres formas conocidas de que esto
termine mal, y cada test de acá describe una.
"""
from __future__ import annotations

import pytest

from core.mcp import delegation as d


@pytest.fixture(autouse=True)
def _limpio():
    d._CADENAS.clear()
    yield
    d._CADENAS.clear()


# ── Freno 1: profundidad ─────────────────────────────────────────────────────

def test_the_first_level_can_delegate():
    k = d.chain_key(1, "gugol")
    d.register_root(k, "gugol")
    d.check(k, "gugol", "delichul")  # no levanta


def test_a_delegated_agent_cannot_delegate_again():
    """A → B → C → D es una cadena que nadie pidió y cuesta en cada eslabón."""
    k = d.chain_key(1, "delichul")
    d.adopt(k, {"agents": {"gugol", "delichul"}, "count": 1, "depth": 2})
    with pytest.raises(d.DelegationError, match="tarea delegada"):
        d.check(k, "delichul", "chikilfumi")


# ── Freno 2: ciclos ──────────────────────────────────────────────────────────

def test_an_agent_cannot_delegate_to_itself():
    """El ciclo más corto, y el más fácil de escribir sin querer."""
    k = d.chain_key(1, "gugol")
    with pytest.raises(d.DelegationError, match="a sí mismo"):
        d.check(k, "gugol", "gugol")


def test_calling_back_into_the_chain_is_refused():
    """A llama a B, B llama a A: sin memoria de la cadena no termina nunca."""
    k = d.chain_key(1, "delichul")
    d.adopt(k, {"agents": {"gugol", "delichul"}, "count": 1, "depth": 1})
    with pytest.raises(d.DelegationError, match="ciclo"):
        d.check(k, "delichul", "gugol")


def test_the_child_inherits_the_whole_chain():
    """Sin heredar, el nieto no sabe quién ya participó y el ciclo se cuela."""
    k = d.chain_key(1, "gugol")
    d.adopt(k, {"agents": {"gugol"}, "count": 1, "depth": 1})
    hijo = d.child_state(k, "delichul")
    assert hijo["agents"] == {"gugol", "delichul"}
    assert hijo["depth"] == 2


# ── Freno 3: cantidad ────────────────────────────────────────────────────────

def test_there_is_a_ceiling_per_task():
    """Un coordinador entusiasta reparte la misma tarea a los ocho agentes."""
    k = d.chain_key(1, "gugol")
    d.adopt(k, {"agents": {"gugol"}, "count": d.MAX_PER_ROOT, "depth": 1})
    with pytest.raises(d.DelegationError, match="máximo"):
        d.check(k, "gugol", "delichul")


def test_two_simultaneous_tasks_do_not_share_the_ceiling():
    """La cadena va por corrida raíz: si compartieran tope, dos tareas del
    mismo agente se frenarían entre sí sin ninguna razón."""
    a, b = d.chain_key(10, "gugol"), d.chain_key(11, "gugol")
    d.adopt(a, {"agents": {"gugol"}, "count": d.MAX_PER_ROOT, "depth": 1})
    d.register_root(b, "gugol")
    d.check(b, "gugol", "delichul")  # no levanta


# ── Los motivos vuelven al modelo, no como excepción opaca ───────────────────

def test_a_refusal_explains_itself():
    k = d.chain_key(1, "gugol")
    with pytest.raises(d.DelegationError) as e:
        d.check(k, "gugol", "")
    assert "Falta el nombre" in str(e.value)


@pytest.mark.asyncio
async def test_the_tool_returns_the_reason_instead_of_throwing():
    """El modelo tiene que poder LEER por qué no se pudo y decidir otra cosa."""
    from core.mcp.memory_service import call_tool_async

    r = await call_tool_async("gugol", "ask_agent", {"agent": "gugol", "prompt": "x"}, 1)
    assert r.get("isError") is True
    assert "a sí mismo" in r["content"][0]["text"]


@pytest.mark.asyncio
async def test_missing_arguments_are_a_readable_error():
    from core.mcp.memory_service import call_tool_async

    r = await call_tool_async("gugol", "ask_agent", {"agent": "otro"}, 1)
    assert r.get("isError") is True
    assert "prompt" in r["content"][0]["text"]


# ── El cableado: existir no alcanza, el agente tiene que saberlo ─────────────

def test_the_tool_is_offered_to_the_model():
    from core.mcp.memory_service import MEMORY_TOOL_NAMES, TOOLS

    assert "ask_agent" in {t["name"] for t in TOOLS}
    assert any(n.endswith("__ask_agent") for n in MEMORY_TOOL_NAMES), (
        "sin estar en la allowlist, la herramienta existe y el modelo no la puede llamar"
    )


def test_the_prompt_says_when_not_to_delegate():
    """Delegar por delegar sólo agrega latencia. El prompt tiene que decirlo:
    sin eso, un coordinador reparte todo por reflejo."""
    from core.soul.auto_memory import AUTO_MEMORY_RULES

    assert "Cuándo no" in AUTO_MEMORY_RULES
    assert "Si podés resolverlo, resolvelo" in AUTO_MEMORY_RULES
    assert "valerse por sí solo" in AUTO_MEMORY_RULES, (
        "el delegado no ve la conversación del que llama"
    )


def test_the_allowlist_is_derived_not_hand_written():
    """Una tool nueva que no llegue a la allowlist existe en el servidor y el
    modelo no la puede llamar. Ya pasó una vez."""
    from core.mcp.memory_service import MEMORY_TOOL_NAMES, TOOLS

    assert {n.split("__")[-1] for n in MEMORY_TOOL_NAMES} == {t["name"] for t in TOOLS}


def test_delegated_runs_are_marked_as_such():
    import inspect

    src = inspect.getsource(d.delegate)
    assert 'source="delegation"' in src, (
        "sin marcarlas, una corrida delegada parece pedida por el usuario"
    )


def test_a_hung_delegate_does_not_hang_the_caller():
    import inspect

    src = inspect.getsource(d.delegate)
    assert "wait_for" in src and "TIMEOUT_SECONDS" in src
    assert "cancel" in src, "si se venció, hay que cortarla, no abandonarla corriendo"
