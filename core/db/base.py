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
    """Create tables. In prod we use Alembic; this is for dev/tests."""
    # Import models so they register on Base.metadata
    from core.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
