"""Seed the agents/ folder with the bundled templates so a fresh install is non-empty."""
from __future__ import annotations

import shutil
from pathlib import Path


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    agents_dst = repo / "agents"
    skills_dst = repo / "skills"
    agents_dst.mkdir(parents=True, exist_ok=True)
    skills_dst.mkdir(parents=True, exist_ok=True)

    for src in (repo / "agents-templates").glob("*.md"):
        dst = agents_dst / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            print(f"seeded agent: {dst.name}")

    for src in (repo / "skills-templates").glob("*.md"):
        dst = skills_dst / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            print(f"seeded skill: {dst.name}")

    print("seed complete.")


if __name__ == "__main__":
    main()
