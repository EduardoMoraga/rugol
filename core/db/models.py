"""SQLAlchemy models. Matches ARCHITECTURE.md §3."""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("name", name="uq_agents_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    model: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    source_path: Mapped[str] = mapped_column(String(512))
    body_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="idle")  # idle|running|error|offline
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    runs: Mapped[list["Run"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("name", name="uq_skills_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    source_path: Mapped[str] = mapped_column(String(512))
    body_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    cron_expr: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    agent: Mapped[Agent] = relationship(back_populates="schedules")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id", ondelete="SET NULL"), default=None)
    source: Mapped[str] = mapped_column(String(16))  # schedule|telegram|slack|dashboard|api
    prompt: Mapped[str] = mapped_column(Text)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|completed|failed|cancelled
    exit_code: Mapped[int | None] = mapped_column(Integer, default=None)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    session_id: Mapped[str | None] = mapped_column(String(128), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    agent: Mapped[Agent] = relationship(back_populates="runs")
    messages: Mapped[list["Message"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user|assistant|tool|system
    content_md: Mapped[str] = mapped_column(Text, default="")
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[Run] = relationship(back_populates="messages")


class OntologyNode(Base):
    __tablename__ = "ontology_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(16))  # concept|entity|event
    label: Mapped[str] = mapped_column(String(256), index=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column("meta_json", JSON, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OntologyEdge(Base):
    __tablename__ = "ontology_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    src: Mapped[int] = mapped_column(ForeignKey("ontology_nodes.id", ondelete="CASCADE"), index=True)
    predicate: Mapped[str] = mapped_column(String(64), index=True)
    dst: Mapped[int] = mapped_column(ForeignKey("ontology_nodes.id", ondelete="CASCADE"), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_by_run: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Improvement(Base):
    __tablename__ = "improvements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    proposed_diff_md: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="proposed")  # proposed|approved|rejected|applied
    proposed_by_run: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), default=None)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), default=None)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(16))  # telegram|slack
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    team_name: Mapped[str | None] = mapped_column(String(128), default=None)
    bound_agent_ids: Mapped[list[int] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
