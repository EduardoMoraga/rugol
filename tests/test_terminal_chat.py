"""La terminal: hablarle a un agente desde donde estás trabajando.

Rugol tenía tres puertas de entrada —Telegram, el dashboard, el cron— y ninguna
servía para el momento en que uno está adentro de una carpeta con un problema.

Lo que hace útil a ésta no es que exista, es una decisión: **la carpeta elige el
agente**. Obligar a nombrarlo rompería justo eso.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _chat_module():
    """Se importa por ruta: el archivo tiene guion en el nombre (es un
    ejecutable del launcher, no un módulo del paquete)."""
    spec = importlib.util.spec_from_file_location("rugol_chat", REPO / "cli/rugol-chat.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── La carpeta elige el proyecto ─────────────────────────────────────────────

def test_standing_in_the_project_folder_picks_it(tmp_path: Path):
    m = _chat_module()
    proy = {"slug": "analisis", "workspace_dir": str(tmp_path)}
    assert m.match_project([proy], tmp_path) is proy


def test_a_subfolder_still_belongs_to_the_project(tmp_path: Path):
    m = _chat_module()
    sub = tmp_path / "agosto" / "crudos"
    sub.mkdir(parents=True)
    proy = {"slug": "analisis", "workspace_dir": str(tmp_path)}
    assert m.match_project([proy], sub) is proy


def test_the_most_specific_folder_wins(tmp_path: Path):
    """Bajar al detalle no puede hacerte hablar con el equipo general."""
    m = _chat_module()
    hijo = tmp_path / "mx"
    hijo.mkdir()
    general = {"slug": "datos", "workspace_dir": str(tmp_path)}
    especifico = {"slug": "datos-mx", "workspace_dir": str(hijo)}
    assert m.match_project([general, especifico], hijo) is especifico
    assert m.match_project([especifico, general], hijo) is especifico


def test_an_unrelated_folder_matches_nothing(tmp_path: Path):
    m = _chat_module()
    otra = tmp_path / "otra"
    otra.mkdir()
    proy = {"slug": "analisis", "workspace_dir": str(tmp_path / "proyecto")}
    (tmp_path / "proyecto").mkdir()
    assert m.match_project([proy], otra) is None


def test_projects_without_a_folder_are_ignored(tmp_path: Path):
    m = _chat_module()
    assert m.match_project([{"slug": "x", "workspace_dir": ""}], tmp_path) is None
    assert m.match_project([{"slug": "x"}], tmp_path) is None


def test_a_folder_that_disappeared_does_not_crash_the_terminal(tmp_path: Path):
    m = _chat_module()
    proy = {"slug": "x", "workspace_dir": "/carpeta/que/se/fue"}
    assert m.match_project([proy], tmp_path) is None


# ── El launcher no puede pisar el cwd ────────────────────────────────────────

def test_the_launcher_keeps_the_users_folder():
    """Si el launcher hiciera `cd` al app dir, la carpeta dejaría de elegir
    nada y toda la ergonomía se cae."""
    src = (REPO / "cli/rugol").read_text(encoding="utf-8")
    i = src.index("run_chat() {")
    cuerpo = src[i:src.index("\n}\n", i)]
    assert "cd " not in cuerpo, "el chat tiene que correr en la carpeta del usuario"
    ps1 = (REPO / "cli/rugol.ps1").read_text(encoding="utf-8")
    j = ps1.index("function Invoke-Chat")
    # Sin los comentarios: el propio comentario explica por qué NO se usa
    # -WorkingDirectory, así que nombrarlo no es usarlo.
    cuerpo_ps = "\n".join(
        linea for linea in ps1[j:ps1.index("\n}\n", j)].splitlines()
        if not linea.strip().startswith("#")
    )
    assert "WorkingDirectory" not in cuerpo_ps and "Push-Location" not in cuerpo_ps


@pytest.mark.parametrize("launcher,comandos", [
    ("cli/rugol", ["chat|ask)", "run)"]),
    ("cli/rugol.ps1", ['@("chat", "ask")', '"run"']),
])
def test_both_launchers_expose_the_commands(launcher: str, comandos: list[str]):
    src = (REPO / launcher).read_text(encoding="utf-8")
    for c in comandos:
        assert c in src, f"{launcher} no expone {c}"


# ── El .env con espacios: el bug que apareció al probar la terminal ──────────

def test_the_launcher_parses_the_env_instead_of_executing_it():
    """`set -a; . "$ENV_FILE"` trata el archivo como script.

    Medido: con `SAFETY_DENY_EXTRA=rm -rf /` —un valor con espacios, que es
    exactamente el formato que documenta .env.example— cada comando imprimía
    `-rf: command not found`, y la variable quedaba con la mitad del valor. Un
    freno de seguridad cortado por la mitad es peor que ninguno: `doctor` lo
    reporta como configurado.
    """
    src = (REPO / "cli/rugol").read_text(encoding="utf-8")
    ejecuta = [
        linea for linea in src.splitlines()
        if "set -a" in linea and '. "$ENV_FILE"' in linea
        and not linea.strip().startswith("#")
    ]
    assert ejecuta == [], ejecuta
    assert "load_env_file() {" in src


def test_the_env_parser_survives_spaces_and_junk(tmp_path: Path):
    import subprocess

    env = tmp_path / ".env"
    env.write_text(
        "# comentario\n"
        "\n"
        "SAFETY_DENY_EXTRA=rm -rf /\n"
        'CON_COMILLAS="valor entre comillas"\n'
        "linea sin igual\n"
        "9INVALIDO=x\n"
        "CORE_PORT=8010\n",
        encoding="utf-8",
    )
    src = (REPO / "cli/rugol").read_text(encoding="utf-8")
    fn = src[src.index("load_env_file() {"):]
    fn = fn[: fn.index("\n}\n") + 3]
    guion = f'ENV_FILE="{env}"\n{fn}\nload_env_file\n' + (
        'echo "[$SAFETY_DENY_EXTRA]"; echo "[$CON_COMILLAS]"; echo "[$CORE_PORT]"; '
        'echo "[${9INVALIDO:-no-existe}]" 2>/dev/null || echo "[no-existe]"\n'
    )
    r = subprocess.run(["bash", "-c", guion], capture_output=True, text=True)
    salida = r.stdout
    assert "[rm -rf /]" in salida, "un valor con espacios tiene que llegar entero"
    assert "[valor entre comillas]" in salida, "las comillas envolventes se sacan"
    assert "[8010]" in salida
    assert "command not found" not in r.stderr
