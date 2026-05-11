"""Introspect the FastAPI app to render the list of REST endpoints the
agent can rely on. Injected into every system prompt so agents don't
hallucinate non-existent paths (the 2026-05-11 Telegram-API incident).

The inventory is captured once at app startup (`set_app`) and rendered
on demand. It's cheap to render — a few hundred bytes of markdown.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_app: Any | None = None
_rendered_cache: str | None = None


def set_app(app: Any) -> None:
    """Register the FastAPI app instance. Called once from core.main."""
    global _app, _rendered_cache
    _app = app
    _rendered_cache = None  # invalidate so the next render uses fresh routes


def _collect_routes() -> list[tuple[str, str]]:
    """Return [(method, path), ...] for every JSON endpoint, ignoring docs."""
    if _app is None:
        return []
    out: list[tuple[str, str]] = []
    for route in getattr(_app, "routes", []):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        if path.startswith(("/docs", "/redoc", "/openapi", "/static")):
            continue
        if not path.startswith("/api"):
            continue
        for m in sorted(methods):
            if m in {"HEAD", "OPTIONS"}:
                continue
            out.append((m, path))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def render_endpoint_block(max_lines: int = 80) -> str:
    """Render a markdown block listing every real REST endpoint.

    The block is intentionally terse — one line per endpoint. The agent
    reads it before deciding to call a path; if the path isn't in the
    list, the agent should NOT invent one.
    """
    global _rendered_cache
    if _rendered_cache is not None:
        return _rendered_cache
    routes = _collect_routes()
    if not routes:
        _rendered_cache = ""
        return ""
    lines: list[str] = [
        "## REST endpoints disponibles en Rogologo (lista cerrada)",
        "Estos son los **únicos** paths bajo `/api` que existen. "
        "Si necesitas algo que NO está acá, NO lo inventes — dilo abiertamente.",
        "",
    ]
    shown = 0
    for method, path in routes:
        if shown >= max_lines:
            lines.append(f"_…y {len(routes) - shown} más (omitidos por tope de líneas)._")
            break
        lines.append(f"- `{method} {path}`")
        shown += 1
    _rendered_cache = "\n".join(lines)
    return _rendered_cache
