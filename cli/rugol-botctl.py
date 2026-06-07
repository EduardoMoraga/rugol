#!/usr/bin/env python
"""Manage the Telegram bots config from the CLI (`rugol bot ...`).

Thin wrapper over core.runtime_state so the format stays identical to what
the backend reads. Writes to the same data/settings.json. The launcher
restarts the backend after a mutation so changes take effect.

Usage (called by the `rugol` launcher, not by humans directly):
  python cli/rugol-botctl.py list
  python cli/rugol-botctl.py add  <token> <agent> <label> [users]
  python cli/rugol-botctl.py remove <key>
"""
from __future__ import annotations

import sys

from core import runtime_state as rs


def _current() -> list[dict]:
    """Normalized bots (includes the legacy single token if that's all there is)."""
    return [
        {"token": b["token"], "agent": b["agent"],
         "users": ",".join(str(u) for u in sorted(b["users"])), "label": b["label"]}
        for b in rs.telegram_bots()
    ]


def _save(bots: list[dict]) -> None:
    rs.save({"telegram_bots": bots})


def cmd_list() -> int:
    bots = rs.telegram_bots()
    if not bots:
        print("(sin bots configurados — usá 'rugol bot add')")
        return 0
    print(f"{len(bots)} bot(s) de Telegram:")
    for b in bots:
        users = ",".join(str(u) for u in sorted(b["users"])) or "(nadie)"
        print(f"  • {b['label'] or b['key']:14} key=…{b['key'][-4:]:6} agente={b['agent'] or '-':16} users={users}")
    return 0


def cmd_add(token: str, agent: str, label: str, users: str) -> int:
    token = token.strip()
    if ":" not in token:
        print("ERROR: el token no tiene el formato <id>:<secreto> de BotFather.", file=sys.stderr)
        return 2
    key = token.split(":", 1)[0]
    bots = _current()
    # Reuse the allowlist of the first existing bot if none was given.
    if not users.strip() and bots:
        users = bots[0]["users"]
    bots = [b for b in bots if b["token"].split(":", 1)[0] != key]  # replace if same bot
    bots.append({
        "token": token,
        "agent": (agent or "assistant").strip(),
        "users": users.strip(),
        "label": (label or f"Bot {len(bots) + 1}").strip(),
    })
    _save(bots)
    print(f"Bot agregado: key=…{key[-4:]} agente={agent or 'assistant'} ({len(bots)} bot(s) en total).")
    return 0


def cmd_remove(key: str) -> int:
    key = key.strip()
    bots = _current()
    kept = [b for b in bots if b["token"].split(":", 1)[0] != key and not b["token"].split(":", 1)[0].endswith(key)]
    if len(kept) == len(bots):
        print(f"No encontré un bot con key '{key}'. Usá 'rugol bot list'.", file=sys.stderr)
        return 1
    _save(kept)
    print(f"Bot '{key}' eliminado. Quedan {len(kept)} bot(s).")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        return cmd_list()
    action, rest = argv[0], argv[1:]
    if action == "list":
        return cmd_list()
    if action == "add":
        token = rest[0] if len(rest) > 0 else ""
        agent = rest[1] if len(rest) > 1 else "assistant"
        label = rest[2] if len(rest) > 2 else ""
        users = rest[3] if len(rest) > 3 else ""
        return cmd_add(token, agent, label, users)
    if action == "remove":
        if not rest:
            print("uso: remove <key>", file=sys.stderr)
            return 2
        return cmd_remove(rest[0])
    print(f"acción desconocida: {action}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
