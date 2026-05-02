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
        ]

        def _existing(sync_conn, table: str) -> set[str]:
            return {c["name"] for c in inspect(sync_conn).get_columns(table)}

        for table, column, ddl in nullable_additions:
            cols = await conn.run_sync(_existing, table)
            if column not in cols:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
