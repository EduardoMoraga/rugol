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
    return dt.datetime.now(dt.UTC)


class Project(Base):
    """A project groups a team of agents around a shared mission.

    The unit of mental account in Rugol is the project, not the agent
    (see ADR-005). Each project carries its own mission text, its own
    visual identity (color + lucide icon name), and (Capa 3) a living
    list of "lessons" — bias corrections, decisions, or domain facts the
    team learned and that every run reads as anchor before acting.
    """

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("slug", name="uq_projects_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    mission: Mapped[str] = mapped_column(Text, default="")
    # En HRO un proyecto es una BÚSQUEDA (posición); aquí va su job description.
    job_description: Mapped[str] = mapped_column(Text, default="")
    # Carpeta de CVs conectada a esta búsqueda (fuente local que el screener lee).
    cv_folder: Mapped[str] = mapped_column(Text, default="")
    # Perfil de entrevista de Sofía para esta búsqueda (promotor, merchandising,
    # ejecutivo_comercial, telemarketing, general…). Adapta foco y preguntas.
    interview_profile: Mapped[str] = mapped_column(String(40), default="general")
    color: Mapped[str] = mapped_column(String(16), default="#7280a8")
    icon: Mapped[str] = mapped_column(String(32), default="briefcase")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|archived
    # Capa 3: living list of approved lessons. Each item is
    # {kind: "lesson"|"bias"|"fact", text: str, source: "user"|"reflection",
    #  added_at: iso8601}. Injected into every run's system prompt for the
    # team, anchoring the agents against drift.
    lessons: Mapped[list[dict] | None] = mapped_column("lessons_json", JSON, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    agents: Mapped[list[Agent]] = relationship(back_populates="project")


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
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True,
    )
    # Capa 5: per-agent tool whitelist. None or empty list → use the full
    # claude_code preset (all built-in tools). When set, the runner passes
    # the list to ClaudeAgentOptions.tools and the model sees only those.
    tools: Mapped[list[str] | None] = mapped_column("tools_json", JSON, default=None)
    # Capa 8: per-agent MCP servers. Stored as a dict keyed by server name,
    # each value matching McpServerConfig shape (stdio | sse | http). None
    # or empty → no per-agent MCP servers, just the SDK defaults.
    mcp_servers: Mapped[dict | None] = mapped_column("mcp_servers_json", JSON, default=None)
    # Sprint 8: motor de ejecución — `claude` (default) o `codex`. Viene del
    # frontmatter del .md; la plataforma entera es indiferente al valor salvo
    # el runner que se elige.
    engine: Mapped[str] = mapped_column(String(16), default="claude")
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    project: Mapped[Project | None] = relationship(back_populates="agents")
    runs: Mapped[list[Run]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    schedules: Mapped[list[Schedule]] = relationship(back_populates="agent", cascade="all, delete-orphan")


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


# Estados en los que una corrida ya terminó. Fuente de verdad del backend; el
# dashboard tiene su espejo en `dashboard/src/lib/api.ts` (TERMINAL_RUN_STATUSES)
# y un test compara las dos listas — agregar un estado acá y olvidarse del otro
# lado dejó al chat refrescando para siempre una corrida interrumpida.
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "cancelled", "interrupted"}
)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id", ondelete="SET NULL"), default=None)
    source: Mapped[str] = mapped_column(String(16))  # schedule|telegram|slack|dashboard|api
    prompt: Mapped[str] = mapped_column(Text)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # `interrupted` lo pone core.resilience en el arranque: la corrida estaba
    # viva cuando el core se apagó. Distinto de `failed` a propósito — el
    # agente no falló, y el bucle self-improving no debe contarlo como fracaso.
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|completed|failed|cancelled|interrupted
    exit_code: Mapped[int | None] = mapped_column(Integer, default=None)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    session_id: Mapped[str | None] = mapped_column(String(128), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    final_text: Mapped[str | None] = mapped_column(Text, default=None)
    # Soul-2 (ADR-007): dual-track dispatcher metadata. NULL on runs that
    # bypassed the dispatcher (forced model_override, devil's advocate, etc.).
    track: Mapped[str | None] = mapped_column(String(8), default=None)  # s1|s2|None
    classifier_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    classifier_rationale: Mapped[str | None] = mapped_column(Text, default=None)
    # Soul-3 (ADR-008): the system-prompt version this run executed against.
    # Format: short id from agent-soul/<name>/lineage.json ("001", "002b", …).
    # NULL on runs that pre-date Soul-3 or on agents with no archive yet.
    agent_version_id: Mapped[str | None] = mapped_column(String(32), default=None)
    # Con qué motor corrió. Se guarda por corrida porque un agente puede
    # cambiar de motor, y la vista de una corrida vieja no debe mentir.
    engine: Mapped[str] = mapped_column(String(16), default="claude")

    agent: Mapped[Agent] = relationship(back_populates="runs")
    messages: Mapped[list[Message]] = relationship(back_populates="run", cascade="all, delete-orphan")


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


class ChannelBinding(Base):
    """Maps an external channel (Telegram chat, Slack channel) to one agent.

    When a message arrives on Telegram chat 12345 or Slack channel C0ABC, the
    adapter looks up the binding by (type, external_id) and dispatches to the
    bound agent. Without a binding, the message is rejected with help text —
    we never silently default to a wrong agent (that was Capa 8.5 fix:
    `default_agent="default"` used to crash on every message because no such
    agent exists).

    UNIQUE on (channel_type, external_id) — one binding per channel.
    """

    __tablename__ = "channel_bindings"
    __table_args__ = (
        UniqueConstraint("channel_type", "external_id", name="uq_channel_bindings_chan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_type: Mapped[str] = mapped_column(String(16))  # telegram|slack
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    label: Mapped[str | None] = mapped_column(String(128), default=None)
    # Override de motor para ESTE chat. NULL = usa el del agente.
    # Existe para que `/motor codex` desde Telegram no tenga que reescribir el
    # .md del agente: probar un motor en una conversación no debería cambiar
    # cómo corre ese agente en los horarios ni en el dashboard.
    engine: Mapped[str | None] = mapped_column(String(16), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ChatSession(Base):
    """Persisted conversational session_id per (channel_type, external_id).

    Capa v0.6.x — long-running conversation memory.

    Before this table existed, the Telegram and Slack adapters kept session
    ids only in-memory (`_CHAT_SESSIONS: dict[str, str]`). Restarting uvicorn
    threw away that dict, so the agent forgot the conversation right after
    a backend restart. With this table, the adapter loads on startup and
    persists on every run completion — across restarts, the chat resumes
    where it left off.

    Each (channel_type, external_id) is unique: one chat → one current
    session_id at a time. When the user runs `/reset` (Telegram) or
    `reset` (Slack), the row is deleted and the next message starts fresh.
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint("channel_type", "external_id", name="uq_chat_sessions_chan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_type: Mapped[str] = mapped_column(String(16))  # telegram|slack
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str] = mapped_column(String(128))
    last_used_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class PipelineItem(Base):
    """Item de pipeline de dominio: un prospecto (CRM) o un candidato (HRO).

    Lo poblan los agentes de la variante (crm-hunter/strategist, hro-screener/
    matcher) llamando a /api/pipeline, y el dashboard lo muestra como kanban.
    `kind` separa los dominios; `data` guarda campos libres (empresa, cargo,
    score, evidencia, próximos pasos, etc.). Es la "actividad registrada" que
    el usuario quiere ver: leads y candidatos moviéndose por etapas, con su
    historial de notas.
    """

    __tablename__ = "pipeline_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # lead|candidate
    title: Mapped[str] = mapped_column(String(200))            # empresa / nombre del candidato
    subtitle: Mapped[str | None] = mapped_column(String(300), default=None)  # persona+cargo / rol postulado
    stage: Mapped[str] = mapped_column(String(40), index=True)
    score: Mapped[int | None] = mapped_column(Integer, default=None)  # 1-5 (encaje ICP / fit)
    source_agent: Mapped[str | None] = mapped_column(String(64), default=None)
    # Búsqueda/posición a la que pertenece el candidato (slug del proyecto). HRO.
    project_slug: Mapped[str | None] = mapped_column(String(80), default=None, index=True)
    # Id de la conversación de entrevista (ElevenLabs o in-app). Indexado para
    # idempotencia O(1) en la sync de voz (antes se escaneaba data JSON O(N)).
    conversation_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    notes: Mapped[list[Any]] = mapped_column(JSON, default=list)  # [{at, agent, text}]
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, index=True)


class InterviewLink(Base):
    """Sesión de entrevista EX-ANTE: un link que toma el CANDIDATO (no el
    reclutador). El reclutador lo genera para una búsqueda; el candidato abre
    /interview/<token>, conversa con Sofía y al cerrar entra al pipeline.

    Tabla nueva → create_all la crea sola; no requiere migración."""

    __tablename__ = "interview_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    project_slug: Mapped[str | None] = mapped_column(String(80), default=None)
    candidate_name: Mapped[str | None] = mapped_column(String(200), default=None)
    profile: Mapped[str | None] = mapped_column(String(40), default=None)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
