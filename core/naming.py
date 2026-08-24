"""Cómo se llaman las cosas: una sola implementación para todo el core.

Había dos copias idénticas de `_slugify` (architect y projects) y tres copias
del mismo regex de nombre (agents, skills, projects). Ninguna de las dos
`_slugify` sacaba acentos: `[^a-z0-9]` convierte la `á` en un guion, así que
"análisis de ventas" quedaba como `an-lisis-de-ventas` en un producto que se
usa en español.

Y el Architect escribía el `.md` con el nombre TAL CUAL lo devolvía el modelo.
El prompt le pide minúsculas y guiones, pero un prompt no es una garantía: con
un "Analista BI" el deploy creaba `Analista BI.md`, el watcher lo cargaba
igual, y ese agente no se podía editar nunca más desde el dashboard porque el
PUT valida el nombre. Un agente inmutable, sin un solo error a la vista.
"""
from __future__ import annotations

import re
import unicodedata

# Nombre de agente o skill: minúsculas, dígitos y guiones, 3-64, sin guion en
# las puntas. El dashboard tiene el mismo criterio en `lib/agent-name.ts`.
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
# Los slugs de proyecto admiten más largo (van en la URL, no en un archivo).
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")

NAME_RULE_ES = (
    "El nombre va en minúsculas, 3-64 caracteres, sólo letras, dígitos y "
    "guiones, sin guion al principio ni al final."
)
NAME_RULE_EN = (
    "Name must be lowercase, 3-64 chars, only letters/digits/dashes, "
    "no leading or trailing dash."
)


def slugify(raw: str, *, max_len: int = 80, fallback: str = "") -> str:
    """"Análisis de Ventas" → "analisis-de-ventas".

    Pliega los acentos antes de barrer lo que no es alfanumérico; si no, cada
    tilde se convertía en un guion.
    """
    plegado = unicodedata.normalize("NFD", raw.strip().lower())
    plegado = "".join(c for c in plegado if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", plegado).strip("-")
    s = s[:max_len].rstrip("-")  # el corte no puede dejar un guion final
    return s or fallback
