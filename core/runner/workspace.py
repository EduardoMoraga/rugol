"""Dónde trabaja un agente.

Hasta ahora había una sola respuesta y estaba escrita en el código: el
directorio de la app. Es decir, los agentes corrían dentro del código fuente de
Rugol. Tres consecuencias, y ninguna era obvia mirando la pantalla:

· Lo que un agente guardaba "en el workspace" caía dentro de `~/.rugol/app`, y
  el siguiente `rugol update` lo borraba con un `git reset --hard`.
· Un agente con motor Codex no podía tocar nada afuera: su sandbox
  `workspace-write` lo encierra en el cwd. Pedirle que leyera una carpeta del
  usuario fallaba sin una explicación que sirviera.
· No levantaba el `CLAUDE.md` de la carpeta del usuario — que es justo donde
  suele estar escrito el contexto del proyecto.

Ahora cada proyecto puede apuntar a una carpeta real. Este módulo es el único
lugar que decide cuál se usa, y el único que sabe cuándo NO usarla.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Rutas que no aceptamos ni aunque el usuario insista. No es una lista de
# seguridad —el agente tiene shell y puede llegar a cualquier lado— sino un
# freno contra el dedo equivocado: apuntar un equipo de agentes a la raíz del
# disco no es una decisión, es un typo.
_PROHIBIDAS = ("/", "/etc", "/usr", "/bin", "/sbin", "/var", "/System", "/Library")


def _es_del_sistema(ruta: Path) -> bool:
    """¿La ruta apunta a una carpeta del sistema?

    Hay que comparar contra la forma RESUELTA de las prohibidas, no contra el
    literal: en macOS `/etc` es un symlink a `/private/etc`, así que
    `Path("/etc").resolve()` no coincide con `Path("/etc")` y la comparación
    ingenua dejaba pasar justo las carpetas que queríamos frenar. Medido.
    """
    for crudo in _PROHIBIDAS:
        candidata = Path(crudo)
        if ruta == candidata:
            return True
        try:
            if ruta == candidata.resolve():
                return True
        except OSError:
            continue
    return False


class WorkspaceError(ValueError):
    """La carpeta configurada no sirve, con el motivo adentro."""


def validate_workspace(raw: str) -> Path:
    """Valida una carpeta candidata y devuelve su ruta absoluta.

    Levanta `WorkspaceError` con un motivo legible. Se usa al GUARDAR la
    configuración del proyecto: es el momento en que el usuario está mirando y
    puede corregir. En tiempo de corrida no se levanta nada — ver `resolve`.
    """
    texto = (raw or "").strip()
    if not texto:
        raise WorkspaceError("La carpeta no puede estar vacía.")
    ruta = Path(texto).expanduser()
    if not ruta.is_absolute():
        raise WorkspaceError(
            f"Tiene que ser una ruta absoluta. Recibí: {texto}"
        )
    ruta = Path(ruta.resolve())
    if _es_del_sistema(ruta):
        raise WorkspaceError(
            f"{ruta} es una carpeta del sistema. Elegí una carpeta de trabajo."
        )
    if not ruta.exists():
        raise WorkspaceError(f"No existe: {ruta}")
    if not ruta.is_dir():
        raise WorkspaceError(f"No es una carpeta: {ruta}")
    return ruta


def resolve(project_workspace: str | None, fallback: Path) -> Path:
    """La carpeta donde va a correr ESTA corrida.

    A diferencia de `validate_workspace`, acá no se levanta nada nunca. Una
    carpeta que se movió o un disco externo desconectado no pueden dejar a un
    agente sin correr: se avisa en el log y se cae al comportamiento anterior.
    Fallar la corrida entera por eso sería cambiar un problema visible (el
    agente trabajó en el lugar equivocado) por uno invisible (el schedule de la
    mañana dejó de existir sin que nadie se entere).
    """
    texto = (project_workspace or "").strip()
    if not texto:
        return fallback
    try:
        return validate_workspace(texto)
    except WorkspaceError as e:
        logger.warning(
            "workspace del proyecto inservible (%s) — corro en %s", e, fallback
        )
        return fallback
