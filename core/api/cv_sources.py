"""API de Fuentes de CV (HRO).

La reclutadora configura de dónde bajar candidatos: Pandapé, Chiletrabajo,
Computrabajo, LinkedIn, Google Drive/OneDrive, o una carpeta local. La lista se
guarda en runtime_state (data/settings.json) y la consume el agente `connector`
para armar el flujo de importación y dejar los CVs en el pipeline.

Endpoints (montados bajo /api):
  GET    /api/cv-sources         → lista (credenciales enmascaradas) + tipos
  POST   /api/cv-sources         → agrega una fuente
  DELETE /api/cv-sources/{id}    → elimina una fuente
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import runtime_state

router = APIRouter(prefix="/cv-sources", tags=["cv-sources"])

# Tipos conocidos. `needs_credentials` ayuda a la UI a pedir (o no) un token.
KNOWN_TYPES: list[dict] = [
    {"id": "pandape", "label": "Pandapé", "needs_credentials": True,
     "hint": "Pega el token/API key de Pandapé."},
    {"id": "chiletrabajo", "label": "Chiletrabajo", "needs_credentials": True,
     "hint": "Usuario/clave o token del portal."},
    {"id": "computrabajo", "label": "Computrabajo", "needs_credentials": True,
     "hint": "Usuario/clave o token del portal."},
    {"id": "linkedin", "label": "LinkedIn", "needs_credentials": True,
     "hint": "Token o credenciales de tu cuenta de reclutador."},
    {"id": "drive", "label": "Google Drive / OneDrive", "needs_credentials": False,
     "hint": "Carpeta sincronizada en tu equipo (sin credenciales)."},
    {"id": "folder", "label": "Carpeta local", "needs_credentials": False,
     "hint": "Una carpeta de tu computador con los CVs."},
    {"id": "web", "label": "Otra web / API", "needs_credentials": True,
     "hint": "Describe la fuente; el agente arma la integración."},
]
_VALID = {t["id"] for t in KNOWN_TYPES}


def _public() -> list[dict]:
    return runtime_state.load().as_public_dict().get("cv_sources", [])


@router.get("")
async def list_sources() -> dict:
    return {"sources": _public(), "types": KNOWN_TYPES}


class AddSourceBody(BaseModel):
    type: str
    name: str | None = None
    credentials: str | None = None


@router.post("", status_code=201)
async def add_source(body: AddSourceBody) -> dict:
    kind = (body.type or "").strip().lower()
    if kind not in _VALID:
        raise HTTPException(422, f"Tipo de fuente inválido. Usa uno de: {', '.join(sorted(_VALID))}.")
    label = next((t["label"] for t in KNOWN_TYPES if t["id"] == kind), kind)
    source = {
        "id": uuid.uuid4().hex[:12],
        "type": kind,
        "name": (body.name or "").strip() or label,
        "credentials": (body.credentials or "").strip(),
        "status": "configurada",
    }
    current = list(runtime_state.load().cv_sources or [])
    current.append(source)
    runtime_state.save({"cv_sources": current})
    return {"sources": _public(), "types": KNOWN_TYPES}


@router.delete("/{source_id}", status_code=200)
async def delete_source(source_id: str) -> dict:
    current = list(runtime_state.load().cv_sources or [])
    new = [s for s in current if str(s.get("id")) != source_id]
    if len(new) == len(current):
        raise HTTPException(404, "Fuente no encontrada.")
    runtime_state.save({"cv_sources": new})
    return {"sources": _public(), "types": KNOWN_TYPES}
