#!/usr/bin/env python
"""`rugol sessions` - ver tus sesiones de Claude Code y retomarlas.

Claude Code guarda cada sesion como un .jsonl en
  ~/.claude/projects/<directorio-codificado>/<session-id>.jsonl
Este script las lee (solo lectura), filtra el ruido interno de Rugol
(las corridas de los propios agentes, que viven bajo ~/.rugol), agrupa por
proyecto y, en la vista de detalle, te entrega el comando para retomar.

Uso (lo llama el launcher 'rugol sessions [filtro]'):
  python cli/rugol-sessions.py            -> lista de proyectos por recencia
  python cli/rugol-sessions.py philips    -> sesiones de ese proyecto + resume
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

# UTF-8 a la salida (en Windows la consola puede no serlo por defecto).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
NOW = time.time()

# Prompts internos de Rugol que NO son sesiones de trabajo del usuario.
NOISE_TITLES = (
    "Acabas de terminar un run", "Acabás de terminar un run",
    "Classify this incoming request", "You are proposing focused mutation",
)


def _rel(ts: float) -> str:
    d = NOW - ts
    if d < 3600:
        return f"hace {int(d / 60)} min"
    if d < 86400:
        return f"hace {int(d / 3600)} h"
    return f"hace {int(d / 86400)} d"


def _short(path: str, width: int = 38) -> str:
    p = path.replace(HOME, "~")
    return p if len(p) <= width else "..." + p[-(width - 3):]


def _is_noise(cwd: str | None, dirname: str, title: str | None) -> bool:
    if cwd and ".rugol" in cwd:
        return True
    if "rugol-app" in dirname or "-rugol-app" in dirname:
        return True
    if title and any(title.startswith(n[:20]) for n in NOISE_TITLES):
        return True
    return False


def _parse(fp: str, want_last: bool = False) -> dict:
    """Extract cwd, first-user title, (optional) last-user message, count."""
    cwd = title = last_user = None
    n = 0
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                n += 1
                # cwd/title estan cerca del inicio; no parseamos todo salvo que
                # necesitemos la ultima linea de usuario.
                if not want_last and cwd and title:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if not cwd and d.get("cwd"):
                    cwd = d["cwd"]
                if d.get("type") == "user":
                    m = d.get("message", {})
                    c = m.get("content") if isinstance(m, dict) else None
                    if isinstance(c, str):
                        t = c
                    elif isinstance(c, list):
                        t = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
                    else:
                        t = ""
                    t = t.strip().replace("\n", " ")
                    if t and not t.startswith("<") and not t.startswith("Caveat"):
                        if not title:
                            title = t[:72]
                        last_user = t[:90]
    except Exception:
        pass
    return {"cwd": cwd, "title": title, "last_user": last_user, "count": n}


def _collect(want_last: bool = False) -> list[dict]:
    out = []
    for fp in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
        dirname = os.path.basename(os.path.dirname(fp))
        info = _parse(fp, want_last=want_last)
        if _is_noise(info["cwd"], dirname, info["title"]):
            continue
        cwd = info["cwd"] or dirname.replace("-", "/")
        out.append({
            "fp": fp,
            "sid": os.path.basename(fp)[:-6],  # sin .jsonl
            "cwd": cwd,
            "title": info["title"] or "(sin titulo)",
            "last_user": info["last_user"],
            "count": info["count"],
            "mtime": os.path.getmtime(fp),
        })
    return out


def _resume_cmd(cwd: str, sid: str) -> str:
    if os.name == "nt":
        return f'Set-Location "{cwd}"; claude --resume {sid}'
    return f"cd '{cwd}' && claude --resume {sid}"


def cmd_list() -> int:
    rows = _collect()
    if not rows:
        print("\n  (no encontre sesiones de Claude Code en ~/.claude/projects)\n")
        return 0
    # Agrupar por proyecto (cwd).
    by_proj: dict[str, list[dict]] = {}
    for r in rows:
        by_proj.setdefault(r["cwd"], []).append(r)
    projs = []
    for cwd, ss in by_proj.items():
        ss.sort(key=lambda r: r["mtime"], reverse=True)
        projs.append((ss[0]["mtime"], cwd, ss))
    projs.sort(reverse=True)
    print(f"\n  TUS PROYECTOS EN CLAUDE CODE  -  {len(rows)} sesiones en {len(projs)} proyectos\n")
    print(f"  {'ULTIMA VEZ':<13} {'SES':>4}  {'PROYECTO':<40} EN QUE QUEDASTE")
    print("  " + "-" * 96)
    for mt, cwd, ss in projs[:20]:
        print(f"  {_rel(mt):<13} {len(ss):>4}  {_short(cwd, 40):<40} {ss[0]['title'][:34]}")
    print()
    print("  Detalle de un proyecto:  rugol sessions <palabra>   (ej. rugol sessions philips)")
    print()
    return 0


def cmd_detail(flt: str) -> int:
    rows = [r for r in _collect(want_last=True) if flt.lower() in r["cwd"].lower()]
    if not rows:
        print(f"\n  (sin sesiones que coincidan con '{flt}')\n")
        return 0
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    cwd = rows[0]["cwd"]
    print(f"\n  SESIONES DE: {_short(cwd, 60)}   ({len(rows)})\n")
    for r in rows[:15]:
        print(f"  - {_rel(r['mtime']):<12} {r['count']:>5} msgs   {r['title']}")
        if r["last_user"]:
            print(f"      ultimo: {r['last_user']}")
        print(f"      retomar: {_resume_cmd(r['cwd'], r['sid'])}")
        print()
    return 0


def main(argv: list[str]) -> int:
    if not os.path.isdir(PROJECTS):
        print("\n  Claude Code no tiene sesiones en este equipo (~/.claude/projects no existe).\n")
        return 0
    flt = " ".join(argv).strip()
    return cmd_detail(flt) if flt else cmd_list()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
