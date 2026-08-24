"""La memoria de Rugol, como servicio — fuera de los motores.

El problema que resuelve. Hasta 2.0 las herramientas de memoria se inyectaban
como un servidor MCP *dentro del proceso* del CLI de Claude, con una función
que sólo existe en su SDK. Consecuencia: un agente corriendo en Codex no
recordaba nada. La memoria, que es la fisonomía del producto, estaba atada a
una de las herramientas.

Ahora la memoria vive en el core y se expone por MCP sobre HTTP. Los dos
motores hablan el mismo protocolo:

    Claude   mcp_servers={"rugol-memory": {"type": "http", "url": …}}
    Codex    codex exec -c mcp_servers.rugol_memory.url="…"

Un solo almacén, un solo comportamiento, y cambiar de motor deja de costar la
memoria del agente.

**Identidad por token, no por parámetro.** El diseño in-process garantizaba que
el agente A no pudiera escribir en la memoria de B: el nombre iba capturado en
un closure, sin parámetro que el modelo pudiera falsear. Sobre HTTP hay que
reconstruir esa garantía, porque el agente tiene shell y podría hacer `curl` al
endpoint. Solución: Rugol emite un token por corrida, el token resuelve a un
agente, y el token vive sólo mientras la corrida corre. El modelo nunca ve un
campo `agent_name`.
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "rugol-memory"
MCP_SERVER_VERSION = "2.0.0"
PROTOCOL_VERSION = "2025-06-18"

# Nombres con el prefijo que la SDK de Claude usa para el allowlist.
MEMORY_TOOL_NAMES: tuple[str, ...] = (
    f"mcp__{MCP_SERVER_NAME}__save_memory",
    f"mcp__{MCP_SERVER_NAME}__list_my_memories",
    f"mcp__{MCP_SERVER_NAME}__forget_memory",
    f"mcp__{MCP_SERVER_NAME}__search_memories",
    f"mcp__{MCP_SERVER_NAME}__remember_fact",
    f"mcp__{MCP_SERVER_NAME}__recall_facts",
)

_VALID_KINDS = {"user", "feedback", "project", "reference", "note"}

# Un token vive lo que dure la corrida. El tope existe para que una corrida que
# muere sin avisar no deje el token abierto para siempre.
_TOKEN_TTL_SECONDS = 6 * 60 * 60


@dataclass
class _Grant:
    agent_name: str
    run_id: int | None
    issued_at: float


_grants: dict[str, _Grant] = {}
_lock = threading.Lock()


def issue_token(agent_name: str, run_id: int | None = None) -> str:
    """Un token para esta corrida. Resuelve a este agente y a ninguno más."""
    token = secrets.token_urlsafe(24)
    with _lock:
        _prune_locked()
        _grants[token] = _Grant(agent_name=agent_name, run_id=run_id, issued_at=time.time())
    return token


def revoke_token(token: str) -> None:
    with _lock:
        _grants.pop(token, None)


def resolve_token(token: str) -> str | None:
    """Nombre del agente dueño del token, o None si no vale."""
    with _lock:
        _prune_locked()
        grant = _grants.get(token)
        return grant.agent_name if grant else None


def active_grants() -> int:
    with _lock:
        _prune_locked()
        return len(_grants)


def _prune_locked() -> None:
    cutoff = time.time() - _TOKEN_TTL_SECONDS
    for token in [t for t, g in _grants.items() if g.issued_at < cutoff]:
        _grants.pop(token, None)


# ── Definición de las herramientas ───────────────────────────────────────────
# Las descripciones son parte del producto: son lo único que el modelo lee para
# decidir si guardar algo. Se mantienen alineadas con las que tenía la versión
# in-process, que ya estaban afinadas.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "save_memory",
        "description": (
            "Save a new persistent memory you'll see in every future run. Use for "
            "things future-you should remember: user facts, feedback, project state, "
            "external references. Don't save derivable code details or ephemeral turn "
            "state. To connect this memory to related ones, weave Obsidian wikilinks "
            "like [[other_memory_name]] into the content — that turns your memory into "
            "a navigable graph, not a flat list. Call list_my_memories first to get the "
            "exact names to link."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "short kebab-case slug"},
                "description": {"type": "string", "description": "one line, used for recall"},
                "content": {"type": "string", "description": "the memory itself"},
                "kind": {
                    "type": "string",
                    "enum": sorted(_VALID_KINDS),
                    "description": "user | feedback | project | reference | note",
                },
            },
            "required": ["name", "description", "content"],
        },
    },
    {
        "name": "list_my_memories",
        "description": (
            "List your existing memories. Call this BEFORE save_memory to avoid "
            "duplicating something you already know."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_memories",
        "description": (
            "Search your memories by keyword across name, description and content. "
            "Use it when you suspect you already know something but the list is long."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "remember_fact",
        "description": (
            "Record a fact in the SHARED knowledge graph, as subject → relation → object "
            "(e.g. 'Philips' → 'is_a' → 'client'). Unlike save_memory, which is private to "
            "you, the graph is common ground every agent can read — use it for facts about "
            "the world (people, clients, systems, how things relate), not for notes about "
            "yourself. Writing the same fact twice is safe and changes nothing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "the entity the fact is about"},
                "relation": {
                    "type": "string",
                    "description": "short snake_case predicate, e.g. works_on, is_a, owns",
                },
                "object": {"type": "string", "description": "what the subject relates to"},
            },
            "required": ["subject", "relation", "object"],
        },
    },
    {
        "name": "recall_facts",
        "description": (
            "Read the shared knowledge graph. Pass 'about' to get everything connected to an "
            "entity in either direction, or 'query' to search across subjects, relations and "
            "objects. Call this before asking the user something another agent may already "
            "have recorded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "about": {"type": "string", "description": "an entity label"},
                "query": {"type": "string", "description": "free text to search for"},
            },
        },
    },
    {
        "name": "forget_memory",
        "description": (
            "Delete a memory by filename (e.g. '20260510-user-role.md') or by its name "
            "field. Use when a memory is outdated or wrong — prefer delete+save over "
            "saving a contradictory duplicate."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"file_or_name": {"type": "string"}},
            "required": ["file_or_name"],
        },
    },
]


def _text(text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


_GRAPH_TOOLS = {"remember_fact", "recall_facts"}


async def call_tool_async(agent_name: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Igual que `call_tool`, más las herramientas del grafo, que tocan la DB.

    El grafo es compartido: lo que un agente escribe lo leen todos. Las memorias
    siguen siendo privadas. Esa asimetría es el diseño, no un descuido — el
    grafo es el terreno común y la memoria es la libreta personal.
    """
    if name not in _GRAPH_TOOLS:
        return call_tool(agent_name, name, args)

    from core.ontology.store import get_ontology

    args = args or {}
    store = get_ontology()
    try:
        if name == "remember_fact":
            subject = str(args.get("subject") or "").strip()
            relation = str(args.get("relation") or "").strip()
            obj = str(args.get("object") or "").strip()
            if not subject or not relation or not obj:
                return _text(
                    "remember_fact needs non-empty subject, relation, and object.",
                    is_error=True,
                )
            await store.add_edge(subject, relation, obj)
            logger.info("grafo: %s escribió %s -%s-> %s", agent_name, subject, relation, obj)
            return _text(f"Recorded: {subject} → {relation} → {obj}")

        if name == "recall_facts":
            about = str(args.get("about") or "").strip()
            query = str(args.get("query") or "").strip()
            if about:
                triples = await store.around(about)
                vacio = f"(nothing recorded about '{about}' yet)"
            elif query:
                triples = await store.search(query)
                vacio = f"(nothing in the graph matched '{query}')"
            else:
                return _text("recall_facts needs either 'about' or 'query'.", is_error=True)
            if not triples:
                return _text(vacio)
            return _text("\n".join(f"- {t.src} → {t.predicate} → {t.dst}" for t in triples))

        return _text(f"Unknown tool '{name}'.", is_error=True)

    except Exception as e:
        logger.exception("grafo: la herramienta %s falló para %s", name, agent_name)
        return _text(f"{name} failed: {e}", is_error=True)


def call_tool(agent_name: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una herramienta en nombre de `agent_name`.

    Nunca levanta: un error se devuelve como resultado con `isError`, que es lo
    que el modelo puede leer y corregir.
    """
    from core.memory import add_memory, delete_memory, list_memories

    args = args or {}
    try:
        if name == "save_memory":
            mem_name = str(args.get("name") or "").strip()
            description = str(args.get("description") or "").strip()
            content = str(args.get("content") or "").strip()
            kind = str(args.get("kind") or "note").strip().lower()
            if not mem_name or not description or not content:
                return _text(
                    "save_memory needs non-empty name, description, and content.",
                    is_error=True,
                )
            if kind not in _VALID_KINDS:
                return _text(
                    f"kind must be one of {sorted(_VALID_KINDS)}, got '{kind}'.",
                    is_error=True,
                )
            mem = add_memory(
                agent_name=agent_name, name=mem_name,
                description=description, content=content, kind=kind,
            )
            logger.info("memoria: %s guardó %s (%s)", agent_name, mem.file, kind)
            return _text(f"Saved memory '{mem.name}' [{mem.kind}] as {mem.file}.")

        if name == "list_my_memories":
            mems = list_memories(agent_name)
            if not mems:
                return _text("(no memories yet)")
            return _text("\n".join(
                f"- [{m.kind}] {m.name} — {m.description} ({m.file})" for m in mems
            ))

        if name == "search_memories":
            query = str(args.get("query") or "").strip().lower()
            if not query:
                return _text("search_memories needs a query.", is_error=True)
            hits = []
            for m in list_memories(agent_name):
                haystack = f"{m.name}\n{m.description}\n{getattr(m, 'content', '')}".lower()
                if query in haystack:
                    hits.append(f"- [{m.kind}] {m.name} — {m.description} ({m.file})")
            if not hits:
                return _text(f"(nothing matched '{query}')")
            return _text("\n".join(hits))

        if name == "forget_memory":
            target = str(args.get("file_or_name") or "").strip()
            if not target:
                return _text("forget_memory needs file_or_name.", is_error=True)
            if not delete_memory(agent_name, target):
                return _text(
                    f"No memory matched '{target}'. Try list_my_memories first.",
                    is_error=True,
                )
            logger.info("memoria: %s olvidó %s", agent_name, target)
            return _text(f"Forgot memory '{target}'.")

        return _text(f"Unknown tool '{name}'.", is_error=True)

    except Exception as e:
        logger.exception("memoria: la herramienta %s falló para %s", name, agent_name)
        return _text(f"{name} failed: {e}", is_error=True)


# ── Configuración que cada motor necesita ────────────────────────────────────
def endpoint_url(token: str, port: int | None = None) -> str:
    from core.config import get_settings

    resolved = port or get_settings().CORE_PORT
    return f"http://127.0.0.1:{resolved}/mcp?t={token}"


def claude_server_config(token: str, port: int | None = None) -> dict[str, Any]:
    """Lo que espera `ClaudeAgentOptions.mcp_servers`."""
    return {"type": "http", "url": endpoint_url(token, port)}


def codex_config_overrides(token: str, port: int | None = None) -> list[str]:
    """Los `-c clave=valor` que hacen que `codex exec` vea el mismo servidor.

    Codex nombra los servidores con guión bajo en la config TOML, así que el
    nombre difiere del de Claude; las herramientas son las mismas.
    """
    url = endpoint_url(token, port)
    return [
        "-c", f'mcp_servers.rugol_memory.url="{url}"',
        "-c", 'mcp_servers.rugol_memory.enabled=true',
        # Sin esto Codex somete cada llamada a su revisión automática de riesgo
        # y la corrida vuelve con "la herramienta requiere aprobación". Rugol
        # corre desatendido: no hay nadie a quien preguntarle.
        #
        # El alcance importa: `auto` aplica SÓLO a este servidor, el de memoria
        # de Rugol. Cualquier otra herramienta que el agente quiera usar sigue
        # pasando por la revisión de Codex, y el sandbox no se toca.
        # Valores válidos del CLI: auto | prompt | writes | approve.
        "-c", 'mcp_servers.rugol_memory.default_tools_approval_mode="auto"',
    ]
