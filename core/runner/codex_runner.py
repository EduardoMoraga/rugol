"""Motor Codex — corre agentes con el CLI de OpenAI Codex.

La forma del CLI está verificada contra `codex-cli 0.149.0`, no supuesta:

    codex exec --json --skip-git-repo-check -C <dir> [-m MODEL]
               [--sandbox workspace-write] [-o <archivo>] -

y el prompt entra por **stdin** (por eso el `-` final). Eso no es un detalle:
este repo ya sufrió el límite de largo de la línea de comandos en Windows —
por eso existe `SOUL_INJECT_BODY_MAX_CHARS`. Por stdin no hay límite.

Eventos JSONL que emite, tal como se observaron:

    {"type":"thread.started","thread_id":"<uuid>"}          → session id
    {"type":"turn.started"}
    {"type":"item.started","item":{...,"type":"command_execution","command":"…"}}
    {"type":"item.completed","item":{"type":"agent_message","text":"…"}}
    {"type":"item.completed","item":{"type":"command_execution","exit_code":0,…}}
    {"type":"turn.completed","usage":{"input_tokens":…,"output_tokens":…}}

Diferencias con el motor Claude que NO se pueden esconder:

  - **Sin herramientas in-process.** Las tools de memoria de Rugol se inyectan
    como servidor MCP dentro del proceso usando una función de la SDK de
    Claude. Codex no tiene equivalente, así que un agente en Codex no guarda
    memoria por tool. Se avisa en el log, una vez por corrida.
  - **Los frenos son el sandbox, no un hook.** Codex trae su propio sandbox
    (`workspace-write` por default acá: escribe sólo en el workspace y no
    tiene red). Eso es más fuerte que nuestras regex. Igual evaluamos cada
    comando contra las reglas de `core.safety`: si aparece uno prohibido,
    matamos el proceso. Es detección + corte, no prevención — el comando pudo
    haber arrancado. Queda dicho, no disimulado.
  - **Sin costo reportado.** Codex informa tokens pero no dólares, así que
    `cost_usd` queda en 0.0 en vez de inventarse un número.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path

from core.bus import bus
from core.config import get_settings
from core.runner.base import RunResult

logger = logging.getLogger(__name__)

name = "codex"

# Sandbox por default. `workspace-write` deja escribir en el directorio de
# trabajo y nada más; es el punto medio razonable para un agente desatendido.
DEFAULT_SANDBOX = "workspace-write"
VALID_SANDBOXES = ("read-only", "workspace-write", "danger-full-access")


class CodexNotAvailableError(RuntimeError):
    """El CLI de Codex no está instalado."""


def find_codex() -> str | None:
    """Ruta al CLI de Codex, o None."""
    if explicit := os.environ.get("RUGOL_CODEX_PATH"):
        return explicit if Path(explicit).is_file() else None
    if found := shutil.which("codex"):
        return found
    for candidate in (
        Path.home() / ".hermes/node/bin/codex",
        Path.home() / ".npm-global/bin/codex",
        Path("/usr/local/bin/codex"),
        Path("/opt/homebrew/bin/codex"),
        Path.home() / ".local/bin/codex",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def codex_version(cli_path: str) -> str:
    import subprocess
    try:
        out = subprocess.run([cli_path, "--version"], capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return ""


def auth_status() -> dict:
    """`codex login status` — configuración, no validez.

    Igual que con Claude: esto dice con qué está configurado, no que funcione.
    """
    import subprocess

    cli = find_codex()
    result = {
        "cli_path": cli, "cli_version": "", "logged_in": False,
        "method": "", "error": "",
    }
    if not cli:
        result["error"] = (
            "El CLI de Codex no está instalado. Instalalo con "
            "`npm install -g @openai/codex` y volvé a probar."
        )
        return result
    result["cli_version"] = codex_version(cli)
    try:
        proc = subprocess.run(
            [cli, "login", "status"], capture_output=True, text=True, timeout=45,
            env=_build_env(),
        )
    except Exception as e:
        result["error"] = f"No pude ejecutar el CLI de Codex: {e}"
        return result
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    lowered = text.lower()
    if "logged in" in lowered and "not logged in" not in lowered:
        result["logged_in"] = True
        result["method"] = "api-key" if "api key" in lowered else "chatgpt"
    else:
        result["error"] = text or "La cuenta de Codex no está conectada."
    return result


def _build_env() -> dict[str, str]:
    """Entorno para el subproceso de Codex.

    Simétrico a lo que hace el motor Claude: si hay `OPENAI_API_KEY` en la
    config la pasamos; si no, el CLI usa el login guardado en `~/.codex`.
    Nunca filtramos las credenciales de Claude a Codex.
    """
    settings = get_settings()
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    env.pop("ANTHROPIC_API_KEY", None)
    key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if key:
        env["OPENAI_API_KEY"] = key
    return env


def _resolve_sandbox() -> str:
    raw = (getattr(get_settings(), "CODEX_SANDBOX", "") or DEFAULT_SANDBOX).strip()
    if raw not in VALID_SANDBOXES:
        logger.warning(
            "CODEX_SANDBOX='%s' no es válido — uso '%s'. Válidos: %s",
            raw, DEFAULT_SANDBOX, ", ".join(VALID_SANDBOXES),
        )
        return DEFAULT_SANDBOX
    return raw


def _looks_like_a_claude_model(model: str) -> bool:
    return model.startswith("claude-")


def build_command(
    *,
    cli_path: str,
    workspace_dir: Path,
    model: str | None,
    session_id: str | None,
    output_file: Path,
    extra_config_args: list[str] | None = None,
) -> list[str]:
    """El argv exacto. Separado para poder testearlo sin lanzar nada.

    Ojo con `resume`: acepta MENOS flags que `exec`. No toma `-C` ni
    `--sandbox` (verificado contra codex-cli 0.149.0 — pasarlos da
    "unexpected argument"). El directorio se resuelve por el `cwd` del
    subproceso y el sandbox por override de config, que sí acepta.
    """
    cmd = [cli_path, "exec"]
    sandbox = _resolve_sandbox()
    if session_id:
        # `resume <uuid>` continúa el hilo; el prompt sigue entrando por stdin.
        cmd += ["resume", session_id, "-c", f'sandbox_mode="{sandbox}"']
    else:
        cmd += ["-C", str(workspace_dir), "--sandbox", sandbox]
    cmd += [
        "--json",
        "--skip-git-repo-check",
        "-o", str(output_file),
        # Sin esto, Codex pide aprobación humana para las herramientas MCP y la
        # corrida vuelve con "la herramienta requiere aprobación". Rugol corre
        # desatendido: no hay nadie a quien preguntarle. `never` devuelve los
        # fallos al modelo, que es lo que queremos. La contención sigue siendo
        # el sandbox, que no se toca.
        "-c", 'approval_policy="never"',
    ]
    # Overrides extra (`-c clave=valor`): así entra el servidor de memoria por
    # MCP/HTTP, el mismo que usa Claude.
    if extra_config_args:
        cmd += list(extra_config_args)
    # Si el agente trae un modelo de Claude en el frontmatter, NO lo pasamos:
    # Codex lo rechazaría. Que use su default configurado.
    if model and not _looks_like_a_claude_model(model):
        cmd += ["-m", model]
    cmd.append("-")  # prompt por stdin
    return cmd


def compose_prompt(*, prompt: str, system_context: str | None) -> str:
    """Codex no tiene `--append-system-prompt`, así que el contexto va adelante
    del pedido, delimitado, para que el modelo sepa qué es instrucción y qué es
    la consigna de este turno."""
    if not system_context or not system_context.strip():
        return prompt
    return (
        "===== CONTEXTO PERMANENTE (quién sos y cómo trabajás) =====\n"
        f"{system_context.strip()}\n"
        "===== FIN DEL CONTEXTO =====\n\n"
        "Pedido de este turno:\n"
        f"{prompt}"
    )


async def run(
    *,
    agent_name: str,
    prompt: str,
    workspace_dir: Path,
    model: str | None = None,
    session_id: str | None = None,
    run_id: int | None = None,
    system_context: str | None = None,
    timeout_seconds: float | None = None,
    extra_config_args: list[str] | None = None,
    **ignored,
) -> RunResult:
    """Corre un agente con Codex y devuelve el mismo `RunResult` que Claude."""
    cli = find_codex()
    if not cli:
        raise CodexNotAvailableError(
            "El motor 'codex' está configurado para este agente pero el CLI no está "
            "instalado. Instalalo con `npm install -g @openai/codex` y conectá la "
            "cuenta con `rugol login --codex`."
        )

    if ignored:
        unsupported = sorted(k for k, v in ignored.items() if v)
        if unsupported:
            logger.info(
                "codex: el motor no soporta %s — el agente %s corre sin eso",
                ", ".join(unsupported), agent_name,
            )

    workspace_dir.mkdir(parents=True, exist_ok=True)
    out_file = workspace_dir / f".rugol-codex-{run_id or 'adhoc'}.txt"
    cmd = build_command(
        cli_path=cli, workspace_dir=workspace_dir, model=model,
        session_id=session_id, output_file=out_file,
        extra_config_args=extra_config_args,
    )
    full_prompt = compose_prompt(prompt=prompt, system_context=system_context)

    from core.safety import evaluate_bash, extra_rules_from_settings

    guard_on = bool(getattr(get_settings(), "SAFETY_GUARDS_ENABLED", True))
    extra = extra_rules_from_settings() if guard_on else ()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_build_env(),
        cwd=str(workspace_dir),
    )
    assert proc.stdin is not None and proc.stdout is not None

    texts: list[str] = []
    new_session = session_id
    in_tok = out_tok = 0
    killed_for: str | None = None

    try:
        proc.stdin.write(full_prompt.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()
    except (BrokenPipeError, ConnectionResetError):
        logger.warning("codex: el CLI cerró stdin antes de recibir el prompt")

    async def _pump() -> None:
        nonlocal new_session, in_tok, out_tok, killed_for
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("{"):
                continue  # ruido tipo "Reading additional input from stdin..."
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")
            if etype == "thread.started":
                new_session = event.get("thread_id") or new_session

            elif etype in ("item.started", "item.completed"):
                item = event.get("item") or {}
                itype = item.get("type")

                if itype == "agent_message" and etype == "item.completed":
                    text = str(item.get("text") or "")
                    if text:
                        texts.append(text)
                        await bus.publish("run:message", {
                            "run_id": run_id, "agent": agent_name,
                            "kind": "text", "delta": text,
                        })

                elif itype == "command_execution":
                    command = str(item.get("command") or "")
                    if etype == "item.started":
                        await bus.publish("run:tool", {
                            "run_id": run_id, "agent": agent_name, "tool": "Bash",
                        })
                        verdict = evaluate_bash(command, extra_rules=extra)
                        if guard_on and not verdict.allowed and killed_for is None:
                            # El sandbox de Codex es la defensa principal; esto
                            # es la red secundaria. Cortamos la corrida.
                            killed_for = verdict.reason
                            logger.error(
                                "codex: comando prohibido (%s) en el agente %s — "
                                "corto la corrida. Comando: %.200s",
                                verdict.rule, agent_name, command,
                            )
                            try:
                                proc.kill()
                            except ProcessLookupError:
                                pass
                            return

            elif etype == "turn.completed":
                usage = event.get("usage") or {}
                in_tok = int(usage.get("input_tokens", 0) or 0)
                out_tok = int(usage.get("output_tokens", 0) or 0)

    try:
        await asyncio.wait_for(_pump(), timeout=timeout_seconds) if timeout_seconds else await _pump()
    except TimeoutError:
        logger.error("codex: la corrida excedió %ss — corto", timeout_seconds)
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        killed_for = killed_for or f"La corrida excedió el límite de {timeout_seconds}s."

    stderr_raw = b""
    try:
        _, stderr_raw = await asyncio.wait_for(proc.communicate(), timeout=30)
    except (TimeoutError, ValueError):
        pass

    # `-o` deja el último mensaje en un archivo: más confiable que reconstruirlo
    # de los eventos si alguno se perdió.
    final_text = ""
    try:
        if out_file.is_file():
            final_text = out_file.read_text(encoding="utf-8", errors="replace").strip()
            out_file.unlink(missing_ok=True)
    except OSError:
        pass
    if not final_text:
        final_text = "\n\n".join(t for t in texts if t).strip()

    if killed_for:
        raise RuntimeError(f"[Rugol · freno de seguridad] {killed_for}")

    if not final_text:
        stderr = stderr_raw.decode("utf-8", errors="replace").strip()
        if proc.returncode not in (0, None):
            raise RuntimeError(
                f"codex salió con código {proc.returncode} sin producir respuesta"
                + (f": {stderr[:500]}" if stderr else "")
            )
        final_text = "(run completed with no text output)"

    return RunResult(
        final_text=final_text,
        session_id=new_session,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=0.0,  # Codex no reporta dólares; no lo inventamos.
        engine="codex",
    )
