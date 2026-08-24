"""Skills CRUD via UI."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from core import naming, runtime_state
from core.db import async_session_factory
from core.db.models import Skill
from core.registry.service import upsert_skill_file

router = APIRouter(prefix="/skills", tags=["skills"])

NAME_RE = naming.NAME_RE  # una sola fuente (core/naming)


class SkillDTO(BaseModel):
    id: int
    name: str
    description: str
    body: str | None = None
    source_path: str


class SkillSpec(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str = ""
    body: str

    def to_markdown(self) -> str:
        esc = self.description.replace('"', '\\"')
        return (
            "---\n"
            f"name: {self.name}\n"
            f'description: "{esc}"\n'
            "---\n\n"
            + self.body.strip() + "\n"
        )


def _validate(s: SkillSpec) -> None:
    if not NAME_RE.fullmatch(s.name):
        raise HTTPException(
            status_code=400,
            detail="Skill name must be lowercase, 3-64 chars, only letters/digits/dashes.",
        )
    if not s.body.strip():
        raise HTTPException(status_code=400, detail="Body cannot be empty.")


@router.get("")
async def list_skills() -> list[dict]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(Skill).order_by(Skill.name))).scalars().all()
        return [
            {"id": s.id, "name": s.name, "description": s.description, "source_path": s.source_path}
            for s in rows
        ]


@router.get("/{skill_id}")
async def get_skill(skill_id: int) -> dict:
    async with async_session_factory() as session:
        s = await session.get(Skill, skill_id)
        if s is None:
            raise HTTPException(status_code=404, detail="skill not found")
        return {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "body": s.body,
            "source_path": s.source_path,
        }


@router.post("", status_code=201, response_model=SkillDTO)
async def create_skill(body: SkillSpec) -> SkillDTO:
    _validate(body)
    skills_dir = runtime_state.skills_dir()
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / f"{body.name}.md"
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Skill file already exists: {target.name}")
    target.write_text(body.to_markdown(), encoding="utf-8")
    await upsert_skill_file(target)
    async with async_session_factory() as session:
        s = (await session.execute(select(Skill).where(Skill.name == body.name))).scalar_one_or_none()
        if s is None:
            raise HTTPException(status_code=500, detail="Skill registered but not visible yet.")
        return SkillDTO(id=s.id, name=s.name, description=s.description, body=s.body, source_path=s.source_path)


@router.put("/{skill_id}")
async def update_skill(skill_id: int, body: SkillSpec) -> SkillDTO:
    _validate(body)
    async with async_session_factory() as session:
        s = await session.get(Skill, skill_id)
        if s is None:
            raise HTTPException(status_code=404, detail="skill not found")
        if s.name != body.name:
            raise HTTPException(status_code=400, detail="Renaming is not supported here.")
        path = Path(s.source_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.to_markdown(), encoding="utf-8")
    await upsert_skill_file(path)
    async with async_session_factory() as session:
        s = await session.get(Skill, skill_id)
        return SkillDTO(id=s.id, name=s.name, description=s.description, body=s.body, source_path=s.source_path)
