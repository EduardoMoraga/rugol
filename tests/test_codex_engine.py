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
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"
    assert cmd[cmd.index("-m") + 1] == "gpt-5.6-sol"


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
    # El sandbox viaja por override de config, que resume sí acepta.
    assert 'sandbox_mode="workspace-write"' in cmd


def test_claude_model_is_not_passed_to_codex():
    """Un agente con `model: claude-opus-5` y `engine: codex` no debe romper:
    Codex rechazaría ese id, así que usamos su default."""
    cmd = build_command(
        cli_path="/bin/codex", workspace_dir=Path("/w"), model="claude-opus-5",
        session_id=None, output_file=Path("/w/o.txt"),
    )
    assert "-m" not in cmd


def test_sandbox_falls_back_on_a_bad_value(monkeypatch):
    monkeypatch.setenv("CODEX_SANDBOX", "modo-inventado")
    from core.config import get_settings
    get_settings.cache_clear()
    try:
        cmd = build_command(cli_path="c", workspace_dir=Path("/w"), model=None,
                            session_id=None, output_file=Path("/w/o.txt"))
        assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"
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
