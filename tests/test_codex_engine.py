"""Motor Codex: argv correcto, eventos bien traducidos, y el corte de seguridad.

Los tests rápidos usan un CLI falso (un script de shell que escupe el mismo
JSONL que se observó del binario real). Hay además un test marcado `live` que
usa el CLI de verdad y sólo corre si está instalado y logueado.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from core.runner.base import RunResult, normalize_engine
from core.runner.codex_runner import build_command, compose_prompt, find_codex
from core.runner.codex_runner import run as codex_run


# ── Resolución de motor desde el frontmatter ─────────────────────────────────
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "claude"), ("", "claude"), ("claude", "claude"),
        ("codex", "codex"), ("CODEX", "codex"), ("  Codex  ", "codex"),
        ("openai", "codex"), ("gpt", "codex"), ("codex-cli", "codex"),
        ("anthropic", "claude"), ("claude-code", "claude"),
        ("gemini", "claude"),  # desconocido → default, no explota
        ("cualquier-cosa", "claude"),
    ],
)
def test_engine_normalisation(raw, expected):
    assert normalize_engine(raw) == expected


# ── argv ─────────────────────────────────────────────────────────────────────
def test_new_session_command_shape():
    cmd = build_command(
        cli_path="/bin/codex", workspace_dir=Path("/w"), model="gpt-5.6-sol",
        session_id=None, output_file=Path("/w/out.txt"),
    )
    assert cmd[:2] == ["/bin/codex", "exec"]
    assert cmd[-1] == "-", "el prompt entra por stdin: sin eso, Windows rompe con prompts largos"
    assert "--json" in cmd and "--skip-git-repo-check" in cmd
    assert cmd[cmd.index("-C") + 1] == "/w"
    assert cmd[cmd.index("-m") + 1] == "gpt-5.6-sol"
    # `--approve-for-me` es lo único que deja a `codex exec` aprobar una
    # herramienta MCP: `exec` fuerza approval_policy=never y sin esto la
    # memoria de Rugol queda inaccesible. Ya implica workspace-write, y no se
    # puede combinar con --sandbox.
    assert "--approve-for-me" in cmd
    assert "--sandbox" not in cmd


def test_resume_omits_flags_that_resume_rejects():
    """`codex exec resume` NO acepta -C ni --sandbox (codex-cli 0.149.0).
    Pasarlos daba "unexpected argument" y la continuación fallaba."""
    cmd = build_command(
        cli_path="/bin/codex", workspace_dir=Path("/w"), model=None,
        session_id="uuid-123", output_file=Path("/w/out.txt"),
    )
    assert cmd[1:4] == ["exec", "resume", "uuid-123"]
    assert "-C" not in cmd
    assert "--sandbox" not in cmd
    # `resume` tampoco acepta --approve-for-me: hay que usar el equivalente por
    # config. Este test existía y afirmaba lo contrario — se había ajustado para
    # que coincidiera con el código en vez de verificarlo contra el CLI, y por
    # eso la segunda respuesta de cada conversación en Codex se cortaba.
    assert "--approve-for-me" not in cmd
    assert 'approvals_reviewer="auto_review"' in cmd


def test_claude_model_is_not_passed_to_codex():
    """Un agente con `model: claude-opus-5` y `engine: codex` no debe romper:
    Codex rechazaría ese id, así que usamos su default."""
    cmd = build_command(
        cli_path="/bin/codex", workspace_dir=Path("/w"), model="claude-opus-5",
        session_id=None, output_file=Path("/w/o.txt"),
    )
    assert "-m" not in cmd


def test_sandbox_falls_back_on_a_bad_value(monkeypatch):
    """Un valor inválido cae al default, que además habilita --approve-for-me."""
    monkeypatch.setenv("CODEX_SANDBOX", "modo-inventado")
    from core.config import get_settings
    get_settings.cache_clear()
    try:
        cmd = build_command(cli_path="c", workspace_dir=Path("/w"), model=None,
                            session_id=None, output_file=Path("/w/o.txt"))
        assert "--approve-for-me" in cmd
        assert "--sandbox" not in cmd
    finally:
        get_settings.cache_clear()


def test_a_deliberate_non_default_sandbox_is_respected(monkeypatch):
    """Si el usuario eligió otro sandbox a propósito, gana su elección —
    aunque eso cueste las herramientas de memoria. Lo avisa por log."""
    monkeypatch.setenv("CODEX_SANDBOX", "read-only")
    from core.config import get_settings
    get_settings.cache_clear()
    try:
        cmd = build_command(cli_path="c", workspace_dir=Path("/w"), model=None,
                            session_id=None, output_file=Path("/w/o.txt"))
        assert cmd[cmd.index("--sandbox") + 1] == "read-only"
        assert "--approve-for-me" not in cmd
    finally:
        get_settings.cache_clear()


# ── Prompt ───────────────────────────────────────────────────────────────────
def test_context_is_delimited_not_just_concatenated():
    out = compose_prompt(prompt="hacé X", system_context="sos un analista")
    assert "sos un analista" in out and "hacé X" in out
    assert out.index("sos un analista") < out.index("hacé X"), "el contexto va primero"
    assert "CONTEXTO PERMANENTE" in out, "sin delimitador el modelo confunde instrucción con pedido"


def test_prompt_without_context_is_untouched():
    assert compose_prompt(prompt="hola", system_context=None) == "hola"
    assert compose_prompt(prompt="hola", system_context="   ") == "hola"


# ── Traducción de eventos, con un CLI falso ──────────────────────────────────
FAKE_EVENTS = """Reading additional input from stdin...
{"type":"thread.started","thread_id":"th-abc-123"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"i0","type":"agent_message","text":"Primera parte."}}
{"type":"item.started","item":{"id":"i1","type":"command_execution","command":"ls -la"}}
{"type":"item.completed","item":{"id":"i1","type":"command_execution","exit_code":0}}
{"type":"item.completed","item":{"id":"i2","type":"agent_message","text":"Segunda parte."}}
{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":20}}
"""


def _fake_cli(tmp_path: Path, events: str, *, write_output: str | None = None) -> Path:
    """Un CLI de mentira que imita al real: lee stdin, escupe JSONL, y opcionalmente
    escribe el último mensaje en el archivo de `-o`."""
    script = tmp_path / "fake-codex"
    body = [
        "#!/usr/bin/env python3",
        "import sys",
        "sys.stdin.read()",
        "argv = sys.argv[1:]",
        f"sys.stdout.write({events!r})",
        "sys.stdout.flush()",
    ]
    if write_output is not None:
        body += [
            "if '-o' in argv:",
            "    p = argv[argv.index('-o') + 1]",
            f"    open(p, 'w').write({write_output!r})",
        ]
    script.write_text("\n".join(body) + "\n", encoding="utf-8")
    script.chmod(0o755)
    return script


@pytest.mark.asyncio
async def test_translates_events_into_a_runresult(tmp_path, monkeypatch):
    cli = _fake_cli(tmp_path, FAKE_EVENTS, write_output="Segunda parte.")
    monkeypatch.setenv("RUGOL_CODEX_PATH", str(cli))

    published: list[tuple[str, dict]] = []
    from core import bus as bus_mod

    async def capture(topic, data):
        published.append((topic, data))

    monkeypatch.setattr(bus_mod.bus, "publish", capture)

    result = await codex_run(
        agent_name="t", prompt="hola", workspace_dir=tmp_path / "ws", run_id=7,
    )
    assert isinstance(result, RunResult)
    assert result.engine == "codex"
    assert result.session_id == "th-abc-123", "el thread_id ES el session id"
    assert result.input_tokens == 100 and result.output_tokens == 20
    assert result.cost_usd == 0.0, "Codex no reporta dólares; no se inventan"
    assert result.final_text == "Segunda parte."

    topics = [t for t, _ in published]
    assert topics.count("run:message") == 2, "cada agent_message se strea"
    assert "run:tool" in topics, "un command_execution tiene que verse como tool"


@pytest.mark.asyncio
async def test_falls_back_to_streamed_text_when_output_file_is_missing(tmp_path, monkeypatch):
    """Si `-o` no dejó archivo, reconstruimos del stream en vez de devolver vacío."""
    cli = _fake_cli(tmp_path, FAKE_EVENTS, write_output=None)
    monkeypatch.setenv("RUGOL_CODEX_PATH", str(cli))
    result = await codex_run(agent_name="t", prompt="hola", workspace_dir=tmp_path / "ws")
    assert "Primera parte." in result.final_text
    assert "Segunda parte." in result.final_text


@pytest.mark.asyncio
async def test_missing_cli_says_how_to_fix_it(tmp_path, monkeypatch):
    from core.runner.codex_runner import CodexNotAvailableError

    monkeypatch.setenv("RUGOL_CODEX_PATH", str(tmp_path / "no-existe"))
    monkeypatch.setattr("core.runner.codex_runner.shutil.which", lambda _: None)
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    with pytest.raises(CodexNotAvailableError) as ei:
        await codex_run(agent_name="t", prompt="x", workspace_dir=tmp_path)
    assert "npm install -g @openai/codex" in str(ei.value)


@pytest.mark.asyncio
async def test_forbidden_command_aborts_the_run(tmp_path, monkeypatch):
    """El sandbox de Codex es la defensa principal, pero un comando prohibido
    igual tiene que cortar la corrida."""
    events = (
        '{"type":"thread.started","thread_id":"th-x"}\n'
        '{"type":"item.started","item":{"type":"command_execution","command":"sudo shutdown -h now"}}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"listo"}}\n'
    )
    cli = _fake_cli(tmp_path, events, write_output="listo")
    monkeypatch.setenv("RUGOL_CODEX_PATH", str(cli))
    with pytest.raises(RuntimeError) as ei:
        await codex_run(agent_name="t", prompt="x", workspace_dir=tmp_path / "ws")
    assert "freno de seguridad" in str(ei.value)


@pytest.mark.asyncio
async def test_guards_off_lets_it_through(tmp_path, monkeypatch):
    events = (
        '{"type":"thread.started","thread_id":"th-y"}\n'
        '{"type":"item.started","item":{"type":"command_execution","command":"sudo reboot"}}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n'
    )
    cli = _fake_cli(tmp_path, events, write_output="ok")
    monkeypatch.setenv("RUGOL_CODEX_PATH", str(cli))
    monkeypatch.setenv("SAFETY_GUARDS_ENABLED", "false")
    from core.config import get_settings
    get_settings.cache_clear()
    try:
        result = await codex_run(agent_name="t", prompt="x", workspace_dir=tmp_path / "ws")
        assert result.final_text == "ok"
    finally:
        get_settings.cache_clear()


# ── El dispatcher ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_dispatch_routes_to_the_right_engine(tmp_path, monkeypatch):
    from core.runner import dispatch

    calls: dict[str, dict] = {}

    async def fake_claude(**kw):
        calls["claude"] = kw
        return RunResult("c", None, 0, 0, 0.0, engine="claude")

    async def fake_codex(**kw):
        calls["codex"] = kw
        return RunResult("x", None, 0, 0, 0.0, engine="codex")

    monkeypatch.setattr("core.runner.claude_runner.run_agent", fake_claude)
    monkeypatch.setattr("core.runner.codex_runner.run", fake_codex)

    r = await dispatch.run_with_engine(
        engine="codex", agent_name="a", prompt="p", workspace_dir=tmp_path, model="gpt-5.6-sol",
        agent_body="soy X", soul_context="recordá Y", project_context="misión Z",
    )
    assert r.engine == "codex"
    ctx = calls["codex"]["system_context"]
    assert "soy X" in ctx and "recordá Y" in ctx and "misión Z" in ctx
    assert ctx.index("soy X") < ctx.index("misión Z"), "persona antes que misión"

    r = await dispatch.run_with_engine(
        engine=None, agent_name="a", prompt="p", workspace_dir=tmp_path, model="claude-sonnet-5",
    )
    assert r.engine == "claude", "sin motor declarado → Claude"
    assert "system_context" not in calls["claude"], "el motor Claude usa las capas por separado"


# ── En vivo (sólo si Codex está instalado y logueado) ────────────────────────
def _codex_ready() -> bool:
    if os.environ.get("RUGOL_SKIP_LIVE"):
        return False
    from core.runner.codex_runner import auth_status
    return bool(find_codex()) and auth_status().get("logged_in")


@pytest.mark.skipif(not _codex_ready(), reason="Codex CLI ausente o sin login")
@pytest.mark.asyncio
async def test_live_codex_answers(tmp_path):
    """Contra el binario real. Es el único que prueba que los flags existen."""
    (tmp_path / "d.txt").write_text("1420\n", encoding="utf-8")
    result = await codex_run(
        agent_name="live", workspace_dir=tmp_path, timeout_seconds=240,
        prompt="Leé d.txt con el shell y respondé SÓLO el número que contiene.",
        system_context="Respondés en una línea, sin preámbulo.",
    )
    assert "1420" in result.final_text
    assert result.session_id, "necesitamos el thread_id para poder continuar la sesión"
    assert result.engine == "codex"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))


# ── Catálogo de skills (llegaban a la DB pero no al modelo) ──────────────────
def test_catalogue_tells_the_agent_where_the_file_is():
    from core.registry.skills_catalog import render_catalogue

    out = render_catalogue([
        ("rugol-review", "Revisión de código.", "/home/u/.rugol/skills/rugol-review.md"),
    ])
    assert "rugol-review" in out
    assert "/home/u/.rugol/skills/rugol-review.md" in out, "sin la ruta el agente no la puede leer"
    assert "Read" in out, "hay que decirle CÓMO usarla"


def test_catalogue_is_none_when_there_are_no_skills():
    from core.registry.skills_catalog import render_catalogue
    assert render_catalogue([]) is None


def test_catalogue_caps_the_list_and_says_so():
    from core.registry.skills_catalog import MAX_LISTED, render_catalogue

    many = [(f"s{i}", f"desc {i}", f"/p/s{i}.md") for i in range(MAX_LISTED + 12)]
    out = render_catalogue(many)
    assert out.count("- **") == MAX_LISTED
    assert "12 más" in out, "truncar en silencio hace creer que están todas"


def test_catalogue_truncates_a_runaway_description():
    """Una descripción desbocada no puede comerse el contexto del agente."""
    from core.registry.skills_catalog import render_catalogue

    out = render_catalogue([("s", "x" * 500, "/p/s.md")])
    entry = next(line for line in out.splitlines() if line.startswith("- **s**"))
    assert entry.endswith("…")
    assert len(entry) < 220, f"la línea de la skill quedó en {len(entry)} caracteres"


@pytest.mark.asyncio
async def test_catalogue_reaches_both_engines(tmp_path, monkeypatch):
    """La regresión que esto cubre: las skills existían en la base y en el
    dashboard, y nunca llegaban al modelo."""
    from core.runner import dispatch

    seen: dict[str, dict] = {}

    async def fake_claude(**kw):
        seen["claude"] = kw
        return RunResult("ok", None, 0, 0, 0.0, engine="claude")

    async def fake_codex(**kw):
        seen["codex"] = kw
        return RunResult("ok", None, 0, 0, 0.0, engine="codex")

    monkeypatch.setattr("core.runner.claude_runner.run_agent", fake_claude)
    monkeypatch.setattr("core.runner.codex_runner.run", fake_codex)

    cat = "## Skills disponibles\n- **x** — y\n  `/p/x.md`"
    await dispatch.run_with_engine(engine="claude", agent_name="a", prompt="p",
                                   workspace_dir=tmp_path, model="m", skills_catalogue=cat)
    assert seen["claude"]["skills_catalogue"] == cat

    await dispatch.run_with_engine(engine="codex", agent_name="a", prompt="p",
                                   workspace_dir=tmp_path, model="m", skills_catalogue=cat,
                                   agent_body="soy X")
    assert cat in seen["codex"]["system_context"]


# ── El motor visible y elegible desde la interfaz ─────────────────────────────
# Antes vivía sólo en el frontmatter de un .md: no se veía ni se podía cambiar.

def test_agentspec_writes_engine_only_when_it_is_not_the_default():
    from core.api.agents import AgentSpec

    plain = AgentSpec(name="ag", model="claude-sonnet-5", description="d", body="b")
    assert "engine:" not in plain.to_markdown(), (
        "no ensuciamos el frontmatter de los agentes de siempre"
    )

    codex = AgentSpec(name="ag", model="claude-sonnet-5", description="d", body="b", engine="codex")
    assert "engine: codex" in codex.to_markdown()

    explicit = AgentSpec(name="ag", model="claude-sonnet-5", description="d", body="b",
                         engine="claude")
    assert "engine:" not in explicit.to_markdown()


def test_agentspec_round_trips_through_the_loader(tmp_path):
    """Lo que escribe el formulario tiene que volver a leerse igual."""
    from core.api.agents import AgentSpec
    from core.registry.loader import load_agent_file

    md = tmp_path / "ida-y-vuelta.md"
    spec = AgentSpec(name="ida-y-vuelta", model="claude-sonnet-5", description="d",
                     body="cuerpo", engine="codex")
    md.write_text(spec.to_markdown(), encoding="utf-8")
    assert load_agent_file(md).engine == "codex"


def test_engines_endpoint_carries_what_the_ui_needs():
    """Cada motor tiene que traer su estado y el comando que lo arregla."""
    import asyncio

    from core.api.health import health_engines

    payload = asyncio.run(health_engines())
    engines = {e["name"]: e for e in payload["engines"]}
    assert set(engines) == {"claude", "codex"}

    for name, e in engines.items():
        for field in ("label", "installed", "connected", "connect_command",
                      "install_command", "supports_memory", "default",
                      "models", "default_model", "missing"):
            assert field in e, f"{name} le falta {field}"
        assert e["connect_command"], f"{name} sin comando para conectar"

    assert engines["claude"]["default"] is True
    # 2.0: la memoria salió de los motores, así que los DOS la tienen. Antes
    # este campo era False para Codex y la UI decía que no recordaba; después
    # del cambio decirlo así sería mentir en la otra dirección.
    assert engines["claude"]["supports_memory"] is True
    assert engines["codex"]["supports_memory"] is True
    # Lo que Codex sí sigue sin tener: las tools in-process de Telegram.
    assert engines["codex"]["missing"], "hay que decir qué le falta"
    assert engines["claude"]["missing"] == []
    assert engines["codex"]["connect_command"] == "rugol login --codex"

    # Y cada motor trae SUS modelos: el frontend no debe tener su propia copia.
    for name, e in engines.items():
        assert e["models"], f"{name} sin modelos"
        assert e["default_model"] in [m["value"] for m in e["models"]]


# ── Memoria compartida: el corazón de 2.0 ────────────────────────────────────
# Hasta 2.0 la memoria era un MCP in-process de la SDK de Claude, así que un
# agente en Codex no recordaba nada. Ahora vive en el core, se sirve por MCP
# sobre HTTP, y los dos motores usan el MISMO almacén.

def test_memory_token_resolves_to_one_agent_only():
    """La garantía que había que reconstruir: el agente A no puede escribir en
    la memoria de B. Antes era un closure; ahora es un token."""
    from core.mcp.memory_service import issue_token, resolve_token, revoke_token

    ta = issue_token("agente-a", run_id=1)
    tb = issue_token("agente-b", run_id=2)
    assert resolve_token(ta) == "agente-a"
    assert resolve_token(tb) == "agente-b"
    assert resolve_token("inventado") is None

    revoke_token(ta)
    assert resolve_token(ta) is None, "el token muere con la corrida"
    assert resolve_token(tb) == "agente-b", "revocar uno no toca el otro"


def test_tools_never_take_an_agent_name_parameter():
    """Si el modelo pudiera escribir el nombre del agente, podría falsearlo."""
    from core.mcp.memory_service import TOOLS

    for tool in TOOLS:
        props = tool["inputSchema"].get("properties", {})
        assert "agent_name" not in props, tool["name"]
        assert "agent" not in props, tool["name"]


def test_both_engines_get_the_same_endpoint():
    from core.mcp.memory_service import (
        claude_server_config,
        codex_config_overrides,
        endpoint_url,
        issue_token,
    )

    token = issue_token("compartido", run_id=7)
    url = endpoint_url(token, port=9999)

    claude = claude_server_config(token, port=9999)
    assert claude == {"type": "http", "url": url}

    codex = codex_config_overrides(token, port=9999)
    assert any(url in arg for arg in codex), codex
    assert "-c" in codex


def test_memory_tools_round_trip_through_the_service(tmp_path, monkeypatch):
    """save → list → search → forget, por la misma vía que usan los motores."""
    from core.mcp.memory_service import call_tool

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))

    saved = call_tool("agente-x", "save_memory", {
        "name": "prefiere-breve", "description": "respuestas cortas",
        "content": "Pidió respuestas de una línea.", "kind": "feedback",
    })
    assert saved["isError"] is False, saved
    assert "prefiere-breve" in saved["content"][0]["text"]

    listed = call_tool("agente-x", "list_my_memories", {})["content"][0]["text"]
    assert "prefiere-breve" in listed

    found = call_tool("agente-x", "search_memories", {"query": "cortas"})["content"][0]["text"]
    assert "prefiere-breve" in found
    miss = call_tool("agente-x", "search_memories", {"query": "zzzz"})["content"][0]["text"]
    assert "nothing matched" in miss

    # Aislamiento: otro agente no ve nada.
    other = call_tool("agente-y", "list_my_memories", {})["content"][0]["text"]
    assert "prefiere-breve" not in other

    gone = call_tool("agente-x", "forget_memory", {"file_or_name": "prefiere-breve"})
    assert gone["isError"] is False, gone
    assert "prefiere-breve" not in call_tool(
        "agente-x", "list_my_memories", {})["content"][0]["text"]


def test_bad_tool_input_comes_back_as_a_readable_error(tmp_path, monkeypatch):
    from core.mcp.memory_service import call_tool

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    r = call_tool("a", "save_memory", {"name": "", "description": "d", "content": "c"})
    assert r["isError"] is True and "non-empty" in r["content"][0]["text"]
    r = call_tool("a", "save_memory", {"name": "n", "description": "d",
                                       "content": "c", "kind": "inventado"})
    assert r["isError"] is True and "kind must be" in r["content"][0]["text"]
    r = call_tool("a", "herramienta-que-no-existe", {})
    assert r["isError"] is True


# ── Cambiar de motor no puede costar la corrida ───────────────────────────────
@pytest.mark.parametrize(
    ("engine", "model", "expected"),
    [
        # El modelo del otro motor se traduce al MISMO NIVEL, que es la
        # intención real: si elegiste el rápido, seguís en el rápido.
        ("claude", "gpt-5.6-luna", "claude-haiku-4-5"),
        ("claude", "gpt-5.6-sol", "claude-opus-5"),
        ("claude", "gpt-5.6-terra", "claude-sonnet-5"),
        ("codex", "claude-opus-5", "gpt-5.6-sol"),
        ("codex", "claude-haiku-4-5", "gpt-5.6-luna"),
        ("codex", "claude-sonnet-4-6", "gpt-5.6-terra"),
        # El modelo propio del motor no se toca.
        ("claude", "claude-opus-5", "claude-opus-5"),
        ("codex", "gpt-5.5", "gpt-5.5"),
        # Sin modelo o con basura → el default del motor.
        ("claude", None, "claude-sonnet-5"),
        ("codex", "", "gpt-5.6-terra"),
        ("claude", "no-existe", "claude-sonnet-5"),
    ],
)
def test_model_translates_across_engines(engine, model, expected):
    from core.llm_models import resolve_model
    assert resolve_model(engine, model) == expected


def test_every_engine_choice_belongs_to_its_engine():
    """Que la UI no ofrezca un modelo que ese motor va a rechazar."""
    from core.llm_models import ENGINE_DEFAULT_MODEL, ENGINE_MODEL_CHOICES, belongs_to

    for engine, choices in ENGINE_MODEL_CHOICES.items():
        assert choices, engine
        for value, label in choices:
            assert belongs_to(value, engine), f"{value} no es de {engine}"
            assert label.strip()
        assert belongs_to(ENGINE_DEFAULT_MODEL[engine], engine)


# ── El argv se valida contra el propio --help del CLI ─────────────────────────
# Este es el test que faltaba. Los tres bugs de flags de Codex (`-C` y
# `--sandbox` en resume, después `--approve-for-me` en resume) se descubrieron
# en producción, cortando conversaciones. Cada vez el test unitario pasaba,
# porque afirmaba lo que el código hacía en vez de lo que el CLI acepta.

def _accepted_flags(*subcommand: str) -> set[str]:
    """Flags que `codex <subcomando> --help` declara aceptar."""
    import re
    import subprocess

    from core.runner.codex_runner import find_codex

    cli = find_codex()
    out = subprocess.run([cli, *subcommand, "--help"], capture_output=True,
                         text=True, timeout=60)
    text = out.stdout + out.stderr
    return set(re.findall(r"(--[a-z][a-z0-9-]+)", text)) | set(
        re.findall(r"(?<![\w-])(-[a-zA-Z])(?![\w-])", text)
    )


@pytest.mark.skipif(not find_codex(), reason="Codex CLI ausente")
@pytest.mark.parametrize("session_id", [None, "01a0-uuid-de-prueba"])
def test_every_flag_we_pass_is_one_the_cli_accepts(session_id, tmp_path):
    """Lo que construimos tiene que existir en el CLI, no en nuestra cabeza."""
    from core.runner.codex_runner import build_command, find_codex

    cmd = build_command(
        cli_path=find_codex(), workspace_dir=tmp_path, model="gpt-5.6-terra",
        session_id=session_id, output_file=tmp_path / "o.txt",
        extra_config_args=["-c", 'mcp_servers.x.url="http://127.0.0.1:1/mcp"'],
    )
    accepted = _accepted_flags("exec", "resume") if session_id else _accepted_flags("exec")

    usados = [a for a in cmd if a.startswith("-") and a != "-"]
    for flag in usados:
        assert flag in accepted, (
            f"{'resume' if session_id else 'exec'} NO acepta {flag}. "
            f"Acepta: {sorted(f for f in accepted if f.startswith('--'))}"
        )


@pytest.mark.skipif(not find_codex(), reason="Codex CLI ausente")
def test_the_approval_config_value_is_one_the_cli_knows(tmp_path):
    """`approvals_reviewer` tiene un enum cerrado: un valor inventado tumba la
    corrida con "unknown variant" antes de que el agente diga nada."""
    import subprocess

    from core.runner.codex_runner import find_codex

    out = subprocess.run(
        [find_codex(), "exec", "resume", "--last",
         "-c", 'approvals_reviewer="valor-que-no-existe"', "--json"],
        capture_output=True, text=True, timeout=60,
    )
    texto = out.stdout + out.stderr
    assert "unknown variant" in texto, "esperaba que el CLI rechazara el valor"
    assert "auto_review" in texto, (
        "el valor que usamos tiene que estar entre los que el CLI acepta"
    )
