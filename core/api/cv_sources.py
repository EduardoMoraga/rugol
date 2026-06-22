"""API de Fuentes de CV (HRO).

La reclutadora configura de dónde bajar candidatos: Pandapé, Chiletrabajo,
Computrabajo, LinkedIn, Google Drive/OneDrive, o una carpeta local. La lista se
guarda en runtime_state (data/settings.json) y la consume el agente `connector`.

Además auto-detecta carpetas de nube montadas localmente (OneDrive, Google Drive)
y calcula el ESTADO de cada fuente para que la UI muestre si está conectada.

Endpoints (montados bajo /api):
  GET    /api/cv-sources         → fuentes (con estado) + tipos + detectadas
  POST   /api/cv-sources         → agrega una fuente (con ruta/credencial)
  DELETE /api/cv-sources/{id}    → elimina una fuente
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import runtime_state

router = APIRouter(prefix="/cv-sources", tags=["cv-sources"])

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
_NEEDS_CRED = {t["id"] for t in KNOWN_TYPES if t["needs_credentials"]}
_LOCAL_TYPES = {"drive", "folder"}


def _mask(v: str) -> str:
    return f"…{v[-4:]}" if v and len(v) > 6 else ""


def _detect_local_drives() -> list[dict]:
    """Carpetas de nube montadas localmente (lo que el agente ya 've')."""
    home = Path.home()
    found: list[dict] = []
    seen: set[str] = set()
    cands: list[Path] = []
    try:
        cands += sorted(home.glob("OneDrive*"))
        cands += sorted(home.glob("Google Drive*"))
        cs = home / "Library" / "CloudStorage"
        if cs.is_dir():
            cands += sorted(cs.glob("OneDrive-*"))
            cands += sorted(cs.glob("GoogleDrive-*"))
            cands += sorted(cs.glob("Dropbox*"))
    except OSError:
        pass
    for p in cands:
        try:
            if p.is_dir() and str(p) not in seen:
                seen.add(str(p))
                found.append({"type": "drive", "name": p.name, "path": str(p)})
        except OSError:
            continue
    return found


def _status(s: dict) -> str:
    """conectada | detectada | falta_ruta | falta_credencial | pendiente."""
    kind = s.get("type")
    path = (s.get("path") or "").strip()
    if kind in _LOCAL_TYPES:
        if path:
            try:
                return "conectada" if Path(path).expanduser().is_dir() else "falta_ruta"
            except OSError:
                return "falta_ruta"
        # sin ruta: ¿hay una carpeta de nube detectada que calce?
        return "detectada" if _detect_local_drives() else "falta_ruta"
    if kind in _NEEDS_CRED:
        return "conectada" if s.get("credentials") else "falta_credencial"
    return "pendiente"


def _public_source(s: dict) -> dict:
    return {
        "id": str(s.get("id", "")),
        "type": s.get("type", ""),
        "name": s.get("name", ""),
        "path": s.get("path", ""),
        "credentials_set": bool(s.get("credentials")),
        "credentials_hint": _mask(str(s.get("credentials", ""))),
        "status": _status(s),
    }


def _payload() -> dict:
    raw = list(runtime_state.load().cv_sources or [])
    detected = _detect_local_drives()
    # Marca qué detectadas ya están agregadas (por ruta) para que la UI no duplique.
    used_paths = {(s.get("path") or "") for s in raw}
    detected = [{**d, "added": d["path"] in used_paths} for d in detected]
    return {
        "sources": [_public_source(s) for s in raw],
        "types": KNOWN_TYPES,
        "detected": detected,
    }


@router.get("")
async def list_sources() -> dict:
    return _payload()


class AddSourceBody(BaseModel):
    type: str
    name: str | None = None
    credentials: str | None = None
    path: str | None = None


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
        "path": (body.path or "").strip(),
        "status": "configurada",
    }
    current = list(runtime_state.load().cv_sources or [])
    current.append(source)
    runtime_state.save({"cv_sources": current})
    return _payload()


@router.delete("/{source_id}", status_code=200)
async def delete_source(source_id: str) -> dict:
    current = list(runtime_state.load().cv_sources or [])
    new = [s for s in current if str(s.get("id")) != source_id]
    if len(new) == len(current):
        raise HTTPException(404, "Fuente no encontrada.")
    runtime_state.save({"cv_sources": new})
    return _payload()
