"""Endpoints de administración — operaciones destructivas con guardia explícita.

POST /api/admin/reset?confirm=YES_RESET_EVERYTHING
    Borra: DB, settings runtime, todos los .md de agentes generados.
    Mantiene: skills internas de Rogologo (rogologo-*.md), templates
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
    "rogologo-add-agent.md",
    "rogologo-deploy.md",
    "rogologo-schedule.md",
    "rogologo-self-improve.md",
}


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

    # DB files
    targets.append(REPO_ROOT / "data" / "rogologo.db")
    targets.append(REPO_ROOT / "data" / "scheduler.db")
    # Runtime settings (tokens, dir overrides, etc.)
    targets.append(REPO_ROOT / "data" / "settings.json")

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
            deleted.append(str(p.relative_to(REPO_ROOT)))
        except Exception as e:
            skipped.append({"path": str(p.relative_to(REPO_ROOT)), "reason": str(e)})

    logger.warning("admin.reset: deleted %d files, skipped %d", len(deleted), len(skipped))
    return {
        "deleted": deleted,
        "skipped": skipped,
        "next_step": (
            "Reinicia el backend (uvicorn). Al arrancar recreará la DB vacía "
            "y creará automáticamente el proyecto Workspace."
        ),
    }
