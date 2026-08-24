#!/usr/bin/env python3
"""Backend for `rugol login` / `logout` / `auth` — one place, both platforms.

Why this exists: Rugol runs your agents through the Claude Code CLI that ships
inside `claude-agent-sdk`, not through whatever `claude` sits on your PATH. So
"log in" has to mean "log in on *that* binary", and until v0.7.2 there was no
command that did it — the only way to touch auth was `rugol setup`, which
rewrites the whole `.env`.

Everything here edits `.env` surgically: one key at a time, comments and
unrelated values untouched.

Usage:
  rugol-auth.py status [--json] [--verify]   # --verify hace una llamada real
  rugol-auth.py status --codex               # estado del motor Codex
  rugol-auth.py login             # interactive login on this machine
  rugol-auth.py token             # long-lived token (headless / server)
  rugol-auth.py logout
  rugol-auth.py path
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.runner.claude_cli import (  # noqa: E402
    auth_status,
    cli_version,
    find_cli,
    verify_credentials,
)

RUGOL_HOME = Path(os.environ.get("RUGOL_HOME") or (Path.home() / ".rugol"))
ENV_FILE = Path(os.environ.get("RUGOL_ENV_FILE") or (RUGOL_HOME / ".env"))

BOLD, DIM, GREEN, YELLOW, RED, RESET = (
    ("\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")
    if sys.stdout.isatty() and os.name != "nt"
    else ("", "", "", "", "", "")
)


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def err(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}", file=sys.stderr)


# ── .env surgery ─────────────────────────────────────────────────────────────
def _env_path(path: Path | None = None) -> Path:
    """Resolved at call time, not at import: a default argument would freeze
    ENV_FILE and make RUGOL_ENV_FILE (and tests) silently ineffective."""
    return path if path is not None else ENV_FILE


def read_env_file(path: Path | None = None) -> dict[str, str]:
    path = _env_path(path)
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def set_env_keys(updates: dict[str, str], path: Path | None = None) -> None:
    """Update or append keys, preserving every other line verbatim."""
    path = _env_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def run_env_from_file() -> dict[str, str]:
    """The environment Rugol's core hands the CLI, rebuilt from the .env on disk.

    Mirrors `core.runner.claude_runner._build_env`, but sourced from the file so
    the CLI reports the same thing whether or not the core is running.
    """
    cfg = read_env_file()
    env = dict(os.environ)
    use_sub = (cfg.get("USE_SUBSCRIPTION", "true") or "true").lower() not in ("false", "0", "no")
    token = cfg.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    api_key = cfg.get("ANTHROPIC_API_KEY", "").strip()
    if use_sub:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        else:
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    elif api_key:
        env["ANTHROPIC_API_KEY"] = api_key
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


# ── Commands ─────────────────────────────────────────────────────────────────
def cmd_path() -> int:
    cli_path, source = find_cli()
    if not cli_path:
        err("No encontré el CLI de Claude. Corré `rugol update` para reinstalar el backend.")
        return 1
    print(cli_path)
    print(f"{DIM}origen: {source}{RESET}", file=sys.stderr)
    return 0


def cmd_status(as_json: bool, verify: bool = False) -> int:
    env = run_env_from_file()
    status = auth_status(env=env)
    probe = None
    # `auth status` sólo dice qué credencial está CONFIGURADA: un token revocado
    # sigue apareciendo como conectado. La única respuesta honesta a "¿sirve?"
    # es una llamada real, y cuesta una fracción de centavo — así que va bajo
    # pedido, no en cada consulta.
    if verify and status["logged_in"]:
        probe = verify_credentials(env=env)
        status = {**status, **probe}
    if as_json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
        if not status["logged_in"]:
            return 1
        return 0 if (probe is None or probe["verified"]) else 1

    print()
    print(f"{BOLD}Cuenta de Claude{RESET}")
    if status["cli_path"]:
        ok(f"CLI: {status['cli_version'] or '?'}  {DIM}({status['cli_source']}){RESET}")
    else:
        err("CLI de Claude no encontrado — corré `rugol update`.")
        return 1

    label = {
        "env-token": "token de CLAUDE_CODE_OAUTH_TOKEN (.env)",
        "api-key": "ANTHROPIC_API_KEY (.env)",
        "machine-login": "login de esta máquina (~/.claude)",
    }.get(status["credential_source"], status["credential_source"])

    if status["logged_in"]:
        who = status["account"] or "(sin email)"
        org = f" · {status['organization']}" if status["organization"] else ""
        plan = f" · plan {status['plan']}" if status["plan"] else ""
        ok(f"configurada: {who}{org}{plan}")
        ok(f"credencial en uso: {label}")
        if probe is None:
            print(f"    {DIM}sin comprobar contra el API — `rugol auth --verify` hace la llamada real{RESET}")
        elif probe["verified"]:
            ok("verificada contra el API: la credencial funciona")
        else:
            code = f" ({probe['verify_status']})" if probe.get("verify_status") else ""
            err(f"el API RECHAZÓ la credencial{code}: {probe['verify_error']}")
            print()
            print(f"  Arreglalo con:  {BOLD}rugol login{RESET}")
            print()
            return 1
        # Dos credenciales configuradas a la vez no rompe (el CLI puede caer a
        # la que funciona), pero vuelve ambiguo cualquier diagnóstico.
        cfg = read_env_file()
        if cfg.get("CLAUDE_CODE_OAUTH_TOKEN") and (Path.home() / ".claude").exists():
            warn(
                "hay token en el .env Y login guardado en esta máquina. Funciona, pero "
                "para diagnosticar dejá uno solo (`rugol login` vacía el token)."
            )
        if cfg.get("ANTHROPIC_API_KEY") and cfg.get("CLAUDE_CODE_OAUTH_TOKEN"):
            warn("hay API key y token de suscripción configurados; USE_SUBSCRIPTION decide cuál se usa.")
        print()
        return 0

    err(f"NO conectada — credencial intentada: {label}")
    if status["error"]:
        print(f"    {DIM}{status['error']}{RESET}")
    print()
    print(f"  Arreglalo con:  {BOLD}rugol login{RESET}   {DIM}(o `rugol login --token` en un server){RESET}")
    print()
    return 1


# ── Codex (motor alternativo) ────────────────────────────────────────────────
def cmd_codex_status(as_json: bool) -> int:
    """Estado del CLI de Codex. Simétrico a `status`, con la misma honestidad:
    dice qué está configurado, no que funcione."""
    from core.runner.codex_runner import auth_status as codex_auth

    st = codex_auth()
    if as_json:
        print(json.dumps(st, indent=2, ensure_ascii=False))
        return 0 if st["logged_in"] else 1

    print()
    print(f"{BOLD}Cuenta de Codex (OpenAI){RESET}")
    if not st["cli_path"]:
        err("CLI de Codex no instalado")
        print(f"    {DIM}{st['error']}{RESET}")
        print()
        print(f"  Instalalo con:  {BOLD}npm install -g @openai/codex{RESET}")
        print()
        return 1
    ok(f"CLI: {st['cli_version'] or '?'}")
    if st["logged_in"]:
        ok(f"conectada (método: {st['method'] or '?'})")
        print()
        return 0
    err("NO conectada")
    if st["error"]:
        print(f"    {DIM}{st['error']}{RESET}")
    print()
    print(f"  Arreglalo con:  {BOLD}rugol login --codex{RESET}")
    print()
    return 1


def cmd_codex_login() -> int:
    """`codex login` — flujo OAuth con la cuenta de ChatGPT, o API key."""
    from core.runner.codex_runner import find_codex

    cli = find_codex()
    if not cli:
        err("El CLI de Codex no está instalado.")
        print(f"  Instalalo con:  {BOLD}npm install -g @openai/codex{RESET}")
        return 1
    print()
    print(f"{BOLD}rugol login --codex{RESET} — conectar tu cuenta de OpenAI")
    print(f"  {DIM}Se abre el navegador para autorizar con ChatGPT.{RESET}")
    print()
    rc = subprocess.call([cli, "login"])
    if rc != 0:
        err(f"El login de Codex terminó con código {rc}.")
        return rc
    print()
    return cmd_codex_status(as_json=False)


def _claude_or_die() -> str:
    cli_path, _ = find_cli()
    if not cli_path:
        err("No encontré el CLI de Claude. Corré `rugol update` para reinstalar el backend.")
        raise SystemExit(1)
    return cli_path


def cmd_login() -> int:
    """Interactive browser login, stored under ~/.claude for this OS user."""
    cli_path = _claude_or_die()
    print()
    print(f"{BOLD}rugol login{RESET} — conectar tu cuenta de Claude en esta máquina")
    print(f"  {DIM}CLI: {cli_version(cli_path) or cli_path}{RESET}")
    print()
    # Run the login with a clean auth env: an existing token in the environment
    # would make the CLI report "already authenticated" and skip the flow.
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    rc = subprocess.call([cli_path, "auth", "login"], env=env)
    if rc != 0:
        err(f"El login terminó con código {rc}.")
        return rc

    # The login lives on disk now, so any token in .env would shadow it.
    cfg = read_env_file()
    updates = {"USE_SUBSCRIPTION": "true"}
    if cfg.get("CLAUDE_CODE_OAUTH_TOKEN"):
        updates["CLAUDE_CODE_OAUTH_TOKEN"] = ""
        warn("vacié CLAUDE_CODE_OAUTH_TOKEN en el .env para que no le gane a este login.")
    if cfg.get("ANTHROPIC_API_KEY"):
        updates["ANTHROPIC_API_KEY"] = ""
    set_env_keys(updates)
    ok(f"config actualizada en {ENV_FILE}")
    print()
    return cmd_status(as_json=False, verify=True)


def cmd_token() -> int:
    """Long-lived subscription token — for a server with no interactive session."""
    cli_path = _claude_or_die()
    print()
    print(f"{BOLD}rugol login --token{RESET} — token largo de suscripción (headless)")
    print(f"  {DIM}Autorizá en el navegador y copiá el token que imprime.{RESET}")
    print()
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    env.pop("ANTHROPIC_API_KEY", None)
    rc = subprocess.call([cli_path, "setup-token"], env=env)
    if rc != 0:
        warn(f"`claude setup-token` salió con código {rc}. Podés pegar un token existente.")
    print()
    try:
        token = input("  Pegá el token (Enter para cancelar): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 1
    if not token:
        warn("Cancelado — no toqué el .env.")
        return 1
    set_env_keys({"USE_SUBSCRIPTION": "true", "CLAUDE_CODE_OAUTH_TOKEN": token, "ANTHROPIC_API_KEY": ""})
    ok(f"token guardado en {ENV_FILE}")
    print()
    return cmd_status(as_json=False, verify=True)


def cmd_api_key() -> int:
    """API-key mode — isolated billing, no subscription involved."""
    _claude_or_die()
    print()
    print(f"{BOLD}rugol login --api-key{RESET} — usar una API key de Anthropic")
    print(f"  {DIM}console.anthropic.com → API keys. Empieza con sk-ant-.{RESET}")
    print()
    try:
        key = input("  ANTHROPIC_API_KEY (Enter para cancelar): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 1
    if not key:
        warn("Cancelado — no toqué el .env.")
        return 1
    if not key.startswith("sk-ant-"):
        err("Una API key de Anthropic empieza con 'sk-ant-'. No guardé nada.")
        return 1
    set_env_keys({"USE_SUBSCRIPTION": "false", "ANTHROPIC_API_KEY": key, "CLAUDE_CODE_OAUTH_TOKEN": ""})
    ok(f"API key guardada en {ENV_FILE}")
    print()
    return cmd_status(as_json=False, verify=True)


def cmd_logout() -> int:
    cli_path = _claude_or_die()
    rc = subprocess.call([cli_path, "auth", "logout"])
    cfg = read_env_file()
    if cfg.get("CLAUDE_CODE_OAUTH_TOKEN") or cfg.get("ANTHROPIC_API_KEY"):
        set_env_keys({"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""})
        ok("credenciales borradas del .env")
    if rc == 0:
        ok("sesión cerrada en esta máquina")
    print(f"  {DIM}Volvé a conectar con: rugol login{RESET}")
    return 0


def cmd_env_set(pairs: list[str]) -> int:
    """`rugol-auth env-set KEY=VALUE ...` — upsert quirúrgico del .env.

    Existe para que `rugol setup` deje de reescribir el archivo entero. El
    .env acepta ~40 claves (OPENAI_API_KEY, CODEX_*, SAFETY_*, HONCHO_*,
    SCHEDULER_TIMEZONE, MAX_CONCURRENT_RUNS…) y setup sólo pregunta por once:
    cada re-corrida borraba las otras veintipico sin decir nada. Medido en
    vivo. `rugol login` ya editaba clave por clave desde el Sprint 7; esto le
    da el mismo trato a setup, con la MISMA función.
    """
    updates: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            err(f"esperaba KEY=VALUE, recibí: {pair}")
            return 2
        key, _, value = pair.partition("=")
        key = key.strip()
        if not key:
            err(f"clave vacía en: {pair}")
            return 2
        updates[key] = value
    if not updates:
        err("no me pasaste ninguna clave")
        return 2
    set_env_keys(updates)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rugol-auth", add_help=True)
    sub = parser.add_subparsers(dest="cmd")

    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    p_status.add_argument("--verify", action="store_true", help="real API round trip")
    p_status.add_argument("--codex", action="store_true", help="sólo el motor Codex")

    p_login = sub.add_parser("login")
    p_login.add_argument("--token", action="store_true", help="long-lived subscription token")
    p_login.add_argument("--api-key", action="store_true", dest="api_key")
    p_login.add_argument("--codex", action="store_true", help="conectar la cuenta de OpenAI/Codex")

    sub.add_parser("logout")
    sub.add_parser("path")
    sub.add_parser("token")

    p_env = sub.add_parser("env-set")
    p_env.add_argument("pairs", nargs="+", metavar="KEY=VALUE")

    args = parser.parse_args(argv)
    cmd = args.cmd or "status"

    if cmd == "status":
        as_json = getattr(args, "json", False)
        if getattr(args, "codex", False):
            return cmd_codex_status(as_json)
        rc = cmd_status(as_json=as_json, verify=getattr(args, "verify", False))
        # Si Codex está instalado, mostramos también su estado: tener dos
        # motores y ver sólo uno es exactamente el tipo de ceguera que este
        # comando existe para eliminar.
        if not as_json:
            from core.runner.codex_runner import find_codex
            if find_codex():
                cmd_codex_status(as_json=False)
        return rc
    if cmd == "env-set":
        return cmd_env_set(args.pairs)
    if cmd == "path":
        return cmd_path()
    if cmd == "logout":
        return cmd_logout()
    if cmd == "token":
        return cmd_token()
    if cmd == "login":
        if getattr(args, "codex", False):
            return cmd_codex_login()
        if getattr(args, "api_key", False):
            return cmd_api_key()
        if getattr(args, "token", False):
            return cmd_token()
        return cmd_login()
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
