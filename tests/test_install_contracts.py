"""Lo que un usuario nuevo vive en la primera hora, y lo que los launchers
tienen prohibido volver a hacer.

Todo lo de acá salió de ensayar una instalación limpia en paralelo a la real:
`rugol up` cantó "core saludable" con el core caído, el dashboard quedó
hablándole al puerto de otra aplicación, y re-correr `rugol setup` borró del
`.env` seis claves que el wizard nunca pregunta.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BASH = REPO / "cli/rugol"
PS1 = REPO / "cli/rugol.ps1"
AUTH = REPO / "cli/rugol-auth.py"
INSTALL_SH = REPO / "installer/install.sh"
NEXT_CONFIG = REPO / "dashboard/next.config.ts"


def _bash() -> str:
    return BASH.read_text(encoding="utf-8")


def _ps1() -> str:
    return PS1.read_text(encoding="utf-8")


def _fn(src: str, header: str) -> str:
    """El cuerpo de una función shell, del encabezado a su llave de cierre."""
    start = src.index(header)
    rest = src[start:]
    return rest[: rest.index("\n}\n") + 3]


# ── "Algo respondió" no es "el core arrancó" ──────────────────────────────────
# Con otra aplicación en el puerto, su 307 pasaba por sano: `curl -fs` sólo
# falla con 4xx/5xx y ni sigue el redirect. `rugol up` avisaba "el puerto está
# ocupado por otro proceso — no lo toco" y dos líneas después cantaba verde.

def test_health_carries_an_identity_marker():
    from core.api.health import SERVICE_ID

    assert SERVICE_ID == "rugol-core"


def test_the_health_payload_actually_ships_the_marker():
    from fastapi.testclient import TestClient

    from core.api.health import SERVICE_ID, router

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api")
    body = TestClient(app).get("/api/health").json()
    assert body["service"] == SERVICE_ID, (
        "sin esta marca los launchers no pueden distinguir al core de "
        "cualquier otra app que escuche en el puerto"
    )


@pytest.mark.parametrize("launcher", ["bash", "ps1"])
def test_both_launchers_verify_who_answers(launcher: str):
    from core.api.health import SERVICE_ID

    src = _bash() if launcher == "bash" else _ps1()
    assert SERVICE_ID in src, (
        f"el launcher {launcher} espera al core sin comprobar que el que "
        "contesta sea el core"
    )


def test_the_bash_wait_goes_through_the_verified_check():
    wait = _fn(_bash(), "wait_for_health() {")
    assert "_core_responds" in wait
    assert "curl" not in wait, (
        "el curl a pelo es justo el que aceptaba el 307 de otra aplicación"
    )


def test_no_bare_health_curl_is_left_as_a_liveness_check():
    """Un `curl -fs .../api/health` suelto vuelve a introducir el bug."""
    sospechosas = [
        line.strip()
        for line in _bash().splitlines()
        # sólo `/api/health` exacto: `/api/health/engines` es otro chequeo, y
        # la línea que define `_core_responds` ya exige la marca.
        if '/api/health"' in line and "curl" in line and "rugol-core" not in line
    ]
    # La única permitida: la rama de `status` que distingue "responde pero NO
    # es Rugol", que necesita preguntar sin exigir la marca.
    assert len(sospechosas) == 1, sospechosas
    assert "NO es el core" in _bash()


# ── Si el core no arrancó, no se sigue de largo ───────────────────────────────

def test_up_stops_when_the_port_belongs_to_someone_else():
    up = _fn(_bash(), "cmd_up() {")
    assert "if ! start_backend; then" in up, (
        "`up` ignoraba el fallo de start_backend y arrancaba el dashboard "
        "contra un core que no existía"
    )
    assert "exit 1" in up


def test_windows_checks_the_port_before_launching_uvicorn():
    """El launcher de Windows ni siquiera miraba si el puerto estaba tomado."""
    src = _ps1()
    assert "function Port-Taken" in src
    assert "if (-not (Start-Backend))" in src, (
        "Cmd-Up tiene que honrar el fallo, no seguir hasta Wait-Health"
    )


# ── El puerto del core queda horneado en el build del dashboard ───────────────
# next.config.ts lee NEXT_PUBLIC_API_URL al compilar y Next serializa el destino
# del proxy. Mover CORE_PORT —lo que dice el troubleshooting— dejaba todas las
# páginas rotas sin un solo mensaje.

def test_the_proxy_target_is_still_decided_at_build_time():
    """Si algún día se resuelve en runtime, estos chequeos sobran: que el test
    sea el que avise, y no que queden dando vueltas sin sentido."""
    assert "NEXT_PUBLIC_API_URL" in NEXT_CONFIG.read_text(encoding="utf-8")


@pytest.mark.parametrize("launcher", ["bash", "ps1"])
def test_both_launchers_rebuild_when_the_port_moved(launcher: str):
    if launcher == "bash":
        src = _bash()
        assert "_dashboard_api_port() {" in src
        assert "_rebuild_if_port_changed" in _fn(src, "cmd_up() {")
    else:
        src = _ps1()
        assert "function Dashboard-ApiPort" in src
        assert "Rebuild-IfPortChanged" in src
    assert "routes-manifest.json" in src, (
        "el puerto horneado se lee del manifest, no se adivina"
    )


# ── `rugol setup` no puede borrar lo que no sabe preguntar ────────────────────

def _env_set(tmp_env: Path, *pairs: str) -> None:
    subprocess.run(
        [sys.executable, str(AUTH), "env-set", *pairs],
        check=True,
        env={"PATH": "/usr/bin:/bin", "RUGOL_ENV_FILE": str(tmp_env)},
        capture_output=True,
    )


def test_env_set_preserves_every_key_it_was_not_asked_about(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "# comentario que tiene que sobrevivir\n"
        "USE_SUBSCRIPTION=true\n"
        "DEFAULT_MODEL=claude-sonnet-5\n"
        "OPENAI_API_KEY=sk-proj-loquesea\n"
        "CODEX_SANDBOX=read-only\n"
        "SAFETY_DENY_EXTRA=algo\n"
        "HONCHO_ENABLED=true\n"
        "SESSION_SECRET=elmismodesiempre\n",
        encoding="utf-8",
    )
    _env_set(env, "DEFAULT_MODEL=claude-opus-5", "DEFAULT_AGENT=assistant")
    texto = env.read_text(encoding="utf-8")

    assert "DEFAULT_MODEL=claude-opus-5" in texto
    assert "DEFAULT_AGENT=assistant" in texto
    for sobreviviente in (
        "OPENAI_API_KEY=sk-proj-loquesea",
        "CODEX_SANDBOX=read-only",
        "SAFETY_DENY_EXTRA=algo",
        "HONCHO_ENABLED=true",
        "SESSION_SECRET=elmismodesiempre",
        "# comentario que tiene que sobrevivir",
    ):
        assert sobreviviente in texto, f"setup volvió a borrar {sobreviviente}"


def test_setup_only_writes_the_whole_file_when_there_is_none(tmp_path: Path):
    setup = _fn(_bash(), "cmd_setup() {")
    assert 'if [ ! -f "$ENV_FILE" ]; then' in setup, (
        "el `cat > $ENV_FILE` tiene que estar detrás de la guarda; si no, "
        "cada re-corrida trunca la configuración"
    )
    assert "run_auth env-set" in setup, "la rama de actualización es quirúrgica"


def test_skipping_telegram_does_not_disconnect_your_bots():
    """"Enter para saltar" tiene que saltar. Escribía TELEGRAM_BOTS=[]."""
    setup = _fn(_bash(), "cmd_setup() {")
    rama = setup[setup.index('if [ ! -f "$ENV_FILE" ]; then'):]
    actualizacion = rama[rama.index("else"):]
    assert 'if [ -n "$tg_token" ]; then' in actualizacion
    ps1 = _ps1()
    assert 'if ($tgToken) { $kv +=' in ps1


def test_setup_does_not_rotate_the_session_secret_on_a_rerun():
    setup = _fn(_bash(), "cmd_setup() {")
    actualizacion = setup[setup.index("run_auth env-set") - 1200:]
    assert "SESSION_SECRET" not in actualizacion.split("run_auth env-set")[1][:400]


# ── Sembrar ejemplos: avisar sólo si copiaste algo ────────────────────────────

def test_seeding_copies_only_markdown_and_stays_quiet_when_empty(tmp_path: Path):
    """Copiaba el directorio entero —incluido el `.gitkeep`— y anunciaba
    "Agentes de ejemplo copiados" en una instalación con cero agentes."""
    src = tmp_path / "tpl"
    src.mkdir()
    (src / ".gitkeep").write_text("explicación, no es un agente\n")
    dst = tmp_path / "agents"
    dst.mkdir()

    cuerpo = _fn(_bash(), "_seed_dir() {")
    guion = (
        "ok() { echo \"OK:$*\"; }\n"
        + cuerpo
        + f'\n_seed_dir "{src}" "{dst}" "Agentes de ejemplo"\n'
    )
    salida = subprocess.run(["bash", "-c", guion], capture_output=True, text=True)
    assert salida.stdout.strip() == "", "no había nada que copiar y avisó igual"
    assert not list(dst.iterdir()), "el .gitkeep no es un agente de ejemplo"

    (src / "real.md").write_text("---\nname: real\n---\ncuerpo\n")
    salida = subprocess.run(["bash", "-c", guion], capture_output=True, text=True)
    assert "OK:" in salida.stdout
    assert [p.name for p in dst.iterdir()] == ["real.md"]


def test_the_default_dirs_survive_a_clean_clone():
    """`SKILLS_DIR` apunta acá por defecto; sin archivo versionado, un clone
    limpio no tiene el directorio."""
    for d in ("agents-templates", "skills-templates"):
        assert (REPO / d / ".gitkeep").exists(), f"{d} no sobrevive al clone"


# ── Instalar desde una copia local no puede llevarse el taller entero ─────────

def test_local_source_install_respects_gitignore():
    """Medido: 5 GB de artefactos de build que ningún usuario recibe al clonar."""
    src = INSTALL_SH.read_text(encoding="utf-8")
    assert "--filter=':- .gitignore'" in src


def test_a_parallel_install_does_not_overwrite_the_real_launcher():
    """El ensayo de instalación limpia se hace con otro RUGOL_HOME; el launcher
    iba igual a ~/.local/bin y pisaba el de la instalación que ya funciona."""
    src = INSTALL_SH.read_text(encoding="utf-8")
    assert 'elif [ "$RUGOL_HOME" = "$HOME/.rugol" ]; then BIN_DIR="$HOME/.local/bin"' in src
    assert 'else BIN_DIR="$RUGOL_HOME/bin"' in src
