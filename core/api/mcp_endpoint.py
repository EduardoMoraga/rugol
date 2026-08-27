"""MCP sobre HTTP — el mismo servidor de memoria para los dos motores.

Implementa a mano el subconjunto de JSON-RPC que un servidor MCP de sólo
herramientas necesita: `initialize`, `tools/list`, `tools/call`, `ping`, y las
notificaciones. Son ~100 líneas y se pueden probar contra los CLIs reales, que
es lo que importa; montar una librería con su propio ciclo de vida ASGI
escondía justo la parte que había que verificar.

El agente se identifica por el token en `?t=` (ver `core.mcp.memory_service`),
nunca por un parámetro que el modelo pueda escribir.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from core.mcp.memory_service import (
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    PROTOCOL_VERSION,
    TOOLS,
    call_tool_async,
    resolve_grant,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


def _rpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


async def _handle(
    message: dict[str, Any], agent_name: str, run_id: int | None = None
) -> dict[str, Any] | None:
    """Un mensaje JSON-RPC → la respuesta, o None si era una notificación."""
    method = message.get("method") or ""
    request_id = message.get("id")
    params = message.get("params") or {}

    # Las notificaciones no llevan id y no se responden.
    if request_id is None and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return _rpc_result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
        })

    if method == "ping":
        return _rpc_result(request_id, {})

    if method == "tools/list":
        return _rpc_result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        outcome = await call_tool_async(agent_name, name, args, run_id)
        # El resultado de una herramienta es un `result` válido incluso cuando
        # `isError` viene en True: es un error de la herramienta, no del RPC.
        return _rpc_result(request_id, outcome)

    # Métodos opcionales que algunos clientes prueban: contestar "no tengo"
    # es correcto y evita que el cliente aborte la sesión.
    if method in ("resources/list", "prompts/list"):
        key = method.split("/")[0]
        return _rpc_result(request_id, {key: []})

    if request_id is None:
        return None
    return _rpc_error(request_id, -32601, f"Method not found: {method}")


@router.post("/mcp")
async def mcp_post(request: Request) -> Response:
    """Único endpoint del servidor. El token va en `?t=`."""
    token = request.query_params.get("t") or ""
    agent_name, run_id = resolve_grant(token)
    if not agent_name:
        # 401 y no 403: el cliente puede reintentar con un token válido.
        logger.warning("mcp: token inválido o expirado")
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32001, "message": "Invalid or expired Rugol token"}},
            status_code=401,
        )

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    # Un cliente puede mandar un lote.
    if isinstance(payload, list):
        # Secuencial a propósito: un batch que escribe en el grafo tiene que
        # aplicarse en el orden que el modelo pidió.
        responses = []
        for m in payload:
            r = await _handle(m, agent_name, run_id)
            if r is not None:
                responses.append(r)
        if not responses:
            return Response(status_code=202)
        return JSONResponse(responses)

    if not isinstance(payload, dict):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32600, "message": "Invalid Request"}},
            status_code=400,
        )

    response = await _handle(payload, agent_name, run_id)
    if response is None:
        # Notificación: 202 sin cuerpo es lo que espera el transporte HTTP.
        return Response(status_code=202)
    return JSONResponse(response)


@router.get("/mcp")
async def mcp_get(request: Request) -> Response:
    """Algunos clientes abren un GET para recibir eventos del servidor.

    Este servidor no emite nada por su cuenta —sólo responde herramientas— así
    que devolvemos 405, que el protocolo permite y los clientes toleran. Es
    mejor que dejar una conexión SSE abierta que nunca va a mandar nada.
    """
    return Response(status_code=405, headers={"Allow": "POST"})
