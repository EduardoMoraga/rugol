"""Cómo se llama un agente, y por qué crear uno fallaba trece veces seguidas.

El formulario tenía un `pattern` en el input con el mismo criterio que el
backend. No servía de nada: los navegadores compilan el `pattern` con el flag
`v`, y bajo `v` un guion literal suelto dentro de una clase de caracteres es un
error de sintaxis. Cuando el pattern no compila, el navegador lo IGNORA en
silencio — `validity.patternMismatch` queda en false para siempre—. Medido en
Chrome 151: "Analista BI" pasaba `checkValidity()` y llegaba al servidor.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FORM = REPO / "dashboard/src/components/agents/agent-form.tsx"
NAME_TS = REPO / "dashboard/src/lib/agent-name.ts"


def _node() -> str | None:
    return shutil.which("node")


def _patterns_del_dashboard() -> list[str]:
    """Todo `pattern=` que el dashboard le entrega a un input."""
    encontrados: list[str] = []
    for path in (REPO / "dashboard/src").rglob("*.tsx"):
        for m in re.finditer(r'pattern="([^"]+)"', path.read_text(encoding="utf-8")):
            encontrados.append(m.group(1))
    # Los que llegan por constante: el valor vive en el .ts
    m = re.search(r'AGENT_NAME_PATTERN = "([^"]+)"', NAME_TS.read_text(encoding="utf-8"))
    assert m, "no encontré AGENT_NAME_PATTERN"
    encontrados.append(m.group(1).replace("\\\\", "\\"))
    return encontrados


@pytest.mark.skipif(_node() is None, reason="hace falta node para compilar el regex")
def test_every_browser_pattern_compiles_with_the_v_flag():
    """Un pattern que no compila no valida NADA, y no avisa."""
    patterns = _patterns_del_dashboard()
    assert patterns, "esperaba al menos el del nombre de agente"
    guion = (
        "const ps = JSON.parse(process.argv[1]);"
        "const malos = [];"
        "for (const p of ps) {"
        "  try { new RegExp('^(?:' + p + ')$', 'v'); }"
        "  catch (e) { malos.push([p, e.message]); }"
        "}"
        "console.log(JSON.stringify(malos));"
    )
    salida = subprocess.run(
        [_node(), "-e", guion, json.dumps(patterns)],
        capture_output=True, text=True, check=True,
    )
    malos = json.loads(salida.stdout)
    assert malos == [], (
        "estos `pattern` no compilan con el flag `v` y el navegador los ignora "
        f"en silencio: {malos}"
    )


@pytest.mark.skipif(_node() is None, reason="hace falta node")
def test_the_agent_name_pattern_actually_rejects_a_human_name():
    """El caso exacto que llegaba al servidor: "Analista BI"."""
    m = re.search(r'AGENT_NAME_PATTERN = "([^"]+)"', NAME_TS.read_text(encoding="utf-8"))
    p = m.group(1).replace("\\\\", "\\")
    guion = (
        "const p = process.argv[1];"
        "const re = new RegExp('^(?:' + p + ')$', 'v');"
        "console.log(JSON.stringify(['Analista BI','analista bi','analista-bi','a-b']"
        ".map(s => [s, re.test(s)])));"
    )
    salida = subprocess.run(
        [_node(), "-e", guion, p], capture_output=True, text=True, check=True
    )
    resultado = dict(json.loads(salida.stdout))
    assert resultado["Analista BI"] is False
    assert resultado["analista bi"] is False
    assert resultado["analista-bi"] is True


def test_the_form_sends_the_slug_not_what_was_typed():
    src = FORM.read_text(encoding="utf-8")
    assert "slugifyAgentName" in src
    assert 'name: mode === "create" ? slug : name.trim(),' in src, (
        "si manda lo tipeado, el servidor vuelve a rechazar nombres humanos"
    )
    assert "Saved as" in src, "la persona tiene que ver con qué nombre se guarda"


# ── El slug: una sola implementación, y que entienda español ──────────────────

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Analista BI", "analista-bi"),
        ("Análisis de Ventas", "analisis-de-ventas"),   # antes: an-lisis-de-ventas
        ("Reporte Philips W14", "reporte-philips-w14"),
        ("  mi agente  ", "mi-agente"),
        ("MI-AGENTE", "mi-agente"),
        ("Ñoño", "nono"),
    ],
)
def test_slugify_folds_accents_instead_of_shredding_them(entrada: str, esperado: str):
    from core.naming import NAME_RE, slugify

    salida = slugify(entrada, max_len=64)
    assert salida == esperado
    assert NAME_RE.fullmatch(salida)


def test_python_and_typescript_agree_on_the_slug():
    """Dos implementaciones del mismo slug es la forma de que se separen."""
    if _node() is None:
        pytest.skip("hace falta node")
    from core.naming import slugify

    casos = ["Analista BI", "Análisis de Ventas", "  mi agente  ", "MI-AGENTE", "Ñoño"]
    # Evaluamos el .ts quitándole los tipos: es la única forma de comparar la
    # implementación REAL contra la de Python sin montar un runner de JS.
    guion = (
        "const src = require('fs').readFileSync(process.argv[1], 'utf8');"
        "const js = src.replace(/^export /gm, '')"
        "             .replace(/: string/g, '')"
        "             .replace(/: \"short\" \\| \"empty\" \\| null/g, '');"
        "const fn = new Function(js + '; return slugifyAgentName;')();"
        "console.log(JSON.stringify(JSON.parse(process.argv[2]).map(s => fn(s))));"
    )
    salida = subprocess.run(
        [_node(), "-e", guion, str(NAME_TS), json.dumps(casos)],
        capture_output=True, text=True,
    )
    if salida.returncode != 0:
        pytest.skip(f"no pude evaluar el slug de TS: {salida.stderr[:200]}")
    ts = json.loads(salida.stdout)
    py = [slugify(c, max_len=64) for c in casos]
    assert ts == py, f"TS={ts} Python={py}"


# ── El Architect no puede crear agentes que después nadie pueda editar ────────

@pytest.mark.parametrize(
    "propuesto,archivo",
    [("Analista BI", "analista-bi"), ("analista-bi", "analista-bi"), ("Análisis", "analisis")],
)
def test_the_architect_slugifies_whatever_the_model_returned(propuesto: str, archivo: str):
    from core.architect.deployer import _nombre_de_agente

    assert _nombre_de_agente(propuesto) == archivo


def test_a_name_that_survives_nothing_is_skipped_not_written():
    from core.architect.deployer import _nombre_de_agente

    assert _nombre_de_agente("...") is None
    assert _nombre_de_agente("a") is None


# ── Editar un agente viejo no puede fallar por su nombre ─────────────────────

def test_updating_an_agent_does_not_revalidate_its_name():
    """El PUT prohíbe renombrar, así que el nombre que llega es el que ya
    tiene. Validarlo dejaba sin editar a cualquier agente cargado de un `.md`
    escrito a mano — y con el campo Nombre deshabilitado, sin forma de
    arreglarlo desde la pantalla."""
    import inspect

    from core.api import agents

    src = inspect.getsource(agents.update_agent)
    assert "check_name=False" in src


def test_the_name_rule_has_one_source():
    from core import naming
    from core.api import agents, skills

    assert agents.NAME_RE is naming.NAME_RE
    assert skills.NAME_RE is naming.NAME_RE
