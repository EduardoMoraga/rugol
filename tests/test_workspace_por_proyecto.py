"""La carpeta sobre la que trabaja un equipo de agentes.

Hasta ahora había una sola respuesta, escrita en el código: el directorio de la
app. Los agentes corrían dentro del código fuente de Rugol. Consecuencias que
ninguna pantalla mostraba: lo que generaban lo borraba el siguiente `rugol
update`; un agente de Codex no podía salir de ahí por su sandbox; y nunca
levantaban el CLAUDE.md de la carpeta del usuario, que es donde suele estar
escrito el contexto del proyecto.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from core.runner.workspace import WorkspaceError, resolve, validate_workspace

# ── Validar al guardar: es cuando el usuario puede corregir ──────────────────

def test_a_real_folder_is_accepted(tmp_path: Path):
    assert validate_workspace(str(tmp_path)) == tmp_path.resolve()


def test_a_relative_path_is_refused(tmp_path: Path):
    with pytest.raises(WorkspaceError, match="absoluta"):
        validate_workspace("./datos")


def test_a_folder_that_does_not_exist_is_refused():
    with pytest.raises(WorkspaceError, match="No existe"):
        validate_workspace("/no/existe/en/ninguna/parte")


def test_a_file_is_not_a_folder(tmp_path: Path):
    f = tmp_path / "algo.txt"
    f.write_text("x")
    with pytest.raises(WorkspaceError, match="No es una carpeta"):
        validate_workspace(str(f))


@pytest.mark.parametrize("ruta", ["/", "/etc", "/usr"])
def test_system_folders_are_refused(ruta: str):
    """Apuntar un equipo de agentes a la raíz del disco no es una decisión."""
    with pytest.raises(WorkspaceError, match="sistema"):
        validate_workspace(ruta)


def test_the_tilde_is_expanded():
    assert str(validate_workspace("~")).startswith("/")


# ── Resolver en tiempo de corrida: nunca fallar ──────────────────────────────

def test_no_folder_configured_falls_back(tmp_path: Path):
    assert resolve("", tmp_path) == tmp_path
    assert resolve(None, tmp_path) == tmp_path


def test_a_broken_folder_falls_back_instead_of_killing_the_run(tmp_path: Path):
    """Un disco desconectado no puede hacer desaparecer el brief de la mañana.

    Fallar la corrida cambiaría un problema visible —el agente trabajó en el
    lugar equivocado— por uno invisible: el schedule dejó de existir y nadie se
    entera hasta que alguien pregunta por el informe.
    """
    assert resolve("/carpeta/que/se/fue", tmp_path) == tmp_path


def test_a_configured_folder_wins(tmp_path: Path):
    destino = tmp_path / "Analisis"
    destino.mkdir()
    assert resolve(str(destino), Path("/otra")) == destino.resolve()


# ── El cableado: la corrida y lo que dispara comparten carpeta ───────────────

def test_the_run_uses_the_project_folder():
    import core.runner.orchestrator as orch

    src = inspect.getsource(orch.RuntimeOrchestrator.enqueue)
    assert "resolve_workspace" in src
    assert "workspace_dir=carpeta_proyecto" in src


def test_checkpoint_and_compiler_run_where_the_run_ran():
    """Si la corrida trabajó en /datos, su checkpoint no puede reflexionar
    parado en otra carpeta."""
    import core.runner.orchestrator as orch

    src = inspect.getsource(orch.RuntimeOrchestrator._execute)
    assert src.count("workspace_dir=carpeta") >= 2


def test_the_project_model_carries_the_folder():
    from core.db.models import Project

    assert hasattr(Project, "workspace_dir")


def test_the_column_is_registered_in_the_migrator():
    src = (Path(__file__).resolve().parent.parent / "core/db/base.py").read_text(encoding="utf-8")
    assert '("projects", "workspace_dir"' in src, (
        "agregarla al modelo no la agrega a una base que ya existe"
    )


def test_saving_a_bad_folder_is_a_400_not_a_silent_shrug():
    import core.api.projects as api

    src = inspect.getsource(api._check_workspace)
    assert "HTTPException" in src and "400" in src
