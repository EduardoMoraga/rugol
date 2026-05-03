"""Reset Rogologo a estado de instalación limpia.

Borra: la DB SQLite, los .md de agentes/skills generados durante pruebas,
los settings runtime (tokens, paths overrideados). NO toca los archivos
de catalog (templates curados que viven en código), ni .env.

Uso:
    python scripts/reset.py --dry-run   # muestra qué borraría
    python scripts/reset.py --apply     # ejecuta el reset

Después del reset reiniciar el backend para que las tablas se recreen
limpias y arranque sin agentes (solo el proyecto Workspace que se crea
automáticamente en init_db).

Pensado para llevar la app a otra PC sin arrastrar tus pruebas.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Skills internas del producto Rogologo — viven en el repo, NO se borran.
# Los templates de proyecto (Personal Assistant, Hija aprende, etc.) están
# en core/templates/catalog.py (código Python), no en .md, así que también
# son seguros sin necesidad de proteger nombres aquí.
PROTECTED_SKILL_NAMES: set[str] = {
    "rogologo-add-agent.md",
    "rogologo-deploy.md",
    "rogologo-schedule.md",
    "rogologo-self-improve.md",
}


def list_targets():
    """Devuelve (db_files, runtime_files, agent_md, skill_md)."""
    db_files = [
        REPO_ROOT / "data" / "rogologo.db",
        REPO_ROOT / "data" / "scheduler.db",
    ]
    runtime_files = [
        REPO_ROOT / "data" / "settings.json",
    ]
    agent_md = []
    skill_md = []
    agents_dir = REPO_ROOT / "agents-templates"
    skills_dir = REPO_ROOT / "skills-templates"
    if agents_dir.exists():
        agent_md = list(agents_dir.glob("*.md"))
    if skills_dir.exists():
        skill_md = [p for p in skills_dir.glob("*.md") if p.name not in PROTECTED_SKILL_NAMES]
    return db_files, runtime_files, agent_md, skill_md


def main() -> int:
    ap = argparse.ArgumentParser(description="Reset Rogologo a instalación limpia")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="muestra qué se borraría")
    g.add_argument("--apply", action="store_true", help="aplica el reset")
    args = ap.parse_args()

    db_files, runtime_files, agent_md, skill_md = list_targets()
    total = len(db_files) + len(runtime_files) + len(agent_md) + len(skill_md)
    print(f"Reset de Rogologo en: {REPO_ROOT}")
    print()
    print(f"Base de datos ({len(db_files)}):")
    for p in db_files:
        marker = "EXISTS" if p.exists() else "absent"
        print(f"  [{marker}] {p.relative_to(REPO_ROOT)}")
    print(f"\nRuntime settings ({len(runtime_files)}):")
    for p in runtime_files:
        marker = "EXISTS" if p.exists() else "absent"
        print(f"  [{marker}] {p.relative_to(REPO_ROOT)}")
    print(f"\nAgentes .md generados ({len(agent_md)}):")
    for p in agent_md:
        print(f"  {p.relative_to(REPO_ROOT)}")
    print(f"\nSkills .md generadas ({len(skill_md)}):")
    for p in skill_md:
        print(f"  {p.relative_to(REPO_ROOT)}")
    print()

    if args.dry_run:
        print(f"DRY RUN: {total} archivos serían borrados. Para aplicar: --apply")
        return 0

    deleted = 0
    for p in db_files + runtime_files + agent_md + skill_md:
        if p.exists():
            try:
                p.unlink()
                deleted += 1
            except Exception as e:
                print(f"WARN no pude borrar {p.relative_to(REPO_ROOT)}: {e}")
    print(f"OK: {deleted} archivos borrados.")
    print()
    print("PROXIMO PASO: reinicia el backend (uvicorn). Al arrancar:")
    print("  - Recrea tablas vacias")
    print("  - Crea automaticamente el proyecto 'Workspace'")
    print("  - El dashboard te muestra el OnboardingHero con templates listos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
