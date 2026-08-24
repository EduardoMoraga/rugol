"""Endpoints de administración — operaciones destructivas con guardia explícita.

POST /api/admin/reset?confirm=YES_RESET_EVERYTHING
    Borra: DB, settings runtime, todos los .md de agentes generados.
    Mantiene: skills internas de Rugol (rugol-*.md), templates
    curados que viven en core/templates/catalog.py.

    Después de llamar este endpoint hay que reiniciar el backend para
    que las tablas se recreen y arranque sin agentes (solo Workspace).
    El endpoint no auto-reinicia: matar uvicorn desde el process manager
    es responsabilidad del operador.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.config import REPO_ROOT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


PROTECTED_SKILL_NAMES = {
    "rugol-add-agent.md",
    "rugol-deploy.md",
    "rugol-schedule.md",
    "rugol-self-improve.md",
}


def _legible(p: Path) -> str:
    """Ruta legible sin asumir que está dentro del repo.

    `relative_to(REPO_ROOT)` levanta ValueError para cualquier cosa fuera del
    repo — y desde que el estado vive en RUGOL_DATA_DIR, las memorias están
    fuera. El reset habría devuelto un 500 al llegar al primer archivo de
    memoria: no sólo incompleto, roto.
    """
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


@router.post("/reset")
async def reset_install(confirm: str = "") -> dict:
    """Wipea instalación a estado fresco. Requiere ?confirm=YES_RESET_EVERYTHING.

    No reinicia el backend — el operador debe matar uvicorn y volver a
    levantarlo. Al hacerlo, init_db recrea las tablas vacías y crea
    automáticamente el proyecto Workspace.
    """
    if confirm != "YES_RESET_EVERYTHING":
        raise HTTPException(
            status_code=400,
            detail="Operación destructiva. Llama con ?confirm=YES_RESET_EVERYTHING para confirmar.",
        )

    targets: list[Path] = []

    # DB files + runtime settings. Barremos data_dir() Y la ruta legacy dentro
    # del repo: si no, un reset en una instalación migrada dejaba el estado
    # viejo intacto y "restablecer" no restablecía nada.
    from core.config import data_dir
    for base in {data_dir(), REPO_ROOT / "data"}:
        targets.append(base / "rugol.db")
        targets.append(base / "scheduler.db")
        targets.append(base / "settings.json")

    # Memorias y linaje de evolución. NO estaban: "Restablecer instalación"
    # dejaba atrás todo lo que los agentes habían aprendido y cómo habían
    # evolucionado sus prompts. Una operación destructiva que no destruye lo
    # que promete es peor que ninguna: el usuario cree que arrancó limpio y
    # arrastra memorias de la instalación anterior.
    for base in {data_dir(), REPO_ROOT}:
        for nombre in ("agent-memory", "agent-soul"):
            carpeta = base / nombre
            if carpeta.is_dir():
                targets.extend(p for p in carpeta.rglob("*") if p.is_file())

    # Agent .md (todos — los templates curados están en código)
    agents_dir = REPO_ROOT / "agents-templates"
    if agents_dir.exists():
        targets.extend(agents_dir.glob("*.md"))

    # Skill .md (excepto las internas del producto)
    skills_dir = REPO_ROOT / "skills-templates"
    if skills_dir.exists():
        for p in skills_dir.glob("*.md"):
            if p.name not in PROTECTED_SKILL_NAMES:
                targets.append(p)

    deleted: list[str] = []
    skipped: list[dict] = []
    for p in targets:
        if not p.exists():
            continue
        try:
            p.unlink()
            deleted.append(_legible(p))
        except Exception as e:
            skipped.append({"path": _legible(p), "reason": str(e)})

    logger.warning("admin.reset: deleted %d files, skipped %d", len(deleted), len(skipped))
    return {
        "deleted": deleted,
        "skipped": skipped,
        "next_step": (
            "Reinicia el backend (uvicorn). Al arrancar recreará la DB vacía "
            "y creará automáticamente el proyecto Workspace."
        ),
    }
