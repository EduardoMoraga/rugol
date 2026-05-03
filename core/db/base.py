"""SQLAlchemy async engine + sessionmaker."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

# Ensure SQLite directory exists before engine connects
if _settings.DATABASE_URL.startswith("sqlite"):
    db_path = _settings.DATABASE_URL.split(":///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(_settings.DATABASE_URL, echo=False, future=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create tables. In prod we use Alembic; this is for dev/tests.

    Also runs a tiny defensive migrator that adds nullable columns we have
    introduced after-the-fact, so a returning developer who already has a
    SQLite file does not need to wipe it.
    """
    # Import models so they register on Base.metadata
    from core.db import models  # noqa: F401
    from sqlalchemy import inspect, text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Lightweight column-add migrator. Add (table, column, ddl) here
        # whenever a nullable column is introduced; production deployments
        # should switch to Alembic before this gets long.
        nullable_additions: list[tuple[str, str, str]] = [
            ("runs", "final_text", "TEXT"),
            # ADR-005: agents now belong to a project (nullable; backfilled below).
            ("agents", "project_id", "INTEGER REFERENCES projects(id) ON DELETE SET NULL"),
            # Capa 5: per-agent tool whitelist (JSON array, nullable = preset).
            ("agents", "tools_json", "TEXT"),
            # Capa 3: per-project living list of lessons / biases (JSON array).
            ("projects", "lessons_json", "TEXT"),
            # Capa 8: per-agent MCP servers (JSON dict keyed by server name).
            ("agents", "mcp_servers_json", "TEXT"),
        ]

        def _existing(sync_conn, table: str) -> set[str]:
            return {c["name"] for c in inspect(sync_conn).get_columns(table)}

        for table, column, ddl in nullable_additions:
            cols = await conn.run_sync(_existing, table)
            if column not in cols:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    # ADR-005 backfill: ensure a Workspace project exists and that every
    # orphan agent belongs to it. Idempotent — safe to run on every boot.
    await _ensure_workspace_project()


async def _ensure_workspace_project() -> None:
    """Create the catch-all Workspace project and adopt orphan agents.

    Runs after table creation and column-add migrations. Idempotent: a
    second invocation is a no-op when there are no orphans and Workspace
    already exists.
    """
    from sqlalchemy import select, update
    from core.db.models import Agent, Project

    async with async_session_factory() as session:
        ws = (await session.execute(
            select(Project).where(Project.slug == "workspace")
        )).scalar_one_or_none()
        if ws is None:
            ws = Project(
                slug="workspace",
                name="Workspace",
                description="Catch-all for agents that don't belong to a named project yet.",
                mission=(
                    "This is the default home for any agent in your Rogologo install. "
                    "When you create real projects (Personal Assistant, Marca personal, etc.) "
                    "you can move agents into them — Workspace is just where things land "
                    "before you decide."
                ),
                color="#7280a8",
                icon="briefcase",
            )
            session.add(ws)
            await session.flush()
        await session.execute(
            update(Agent).where(Agent.project_id.is_(None)).values(project_id=ws.id)
        )
        await session.commit()
