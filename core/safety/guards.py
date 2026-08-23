"""Hard denies for commands an unattended agent must never run.

Mechanism: a `PreToolUse` hook. Two reasons it is the right hook rather than
`can_use_tool`:

  1. `can_use_tool` requires the SDK's streaming mode (an AsyncIterable
     prompt); Rugol passes a plain string, so wiring it would mean rewriting
     the runner's call shape.
  2. Hooks fire regardless of `permission_mode`, and Rugol runs on
     `bypassPermissions` by design.

Design rules for this file, learned the hard way about guardrails:

  - **Narrow beats clever.** A rule that also blocks legitimate work gets
    switched off, and then there is no guardrail at all. Every pattern here
    targets a command whose *only* plausible outcome is damage.
  - **Deny, don't warn.** gstack warns and lets a human decide. There is no
    human here.
  - **Say why.** The deny message goes back to the model, so it can adapt
    instead of retrying the same command forever.
  - **Never crash the run.** A bug in a guard must not take down the agent;
    the hook fails open on unexpected errors, and logs loudly.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DenyRule:
    """One thing an agent must not do, and why."""

    name: str
    pattern: re.Pattern[str]
    reason: str


def _rx(p: str) -> re.Pattern[str]:
    return re.compile(p, re.IGNORECASE)


# El comando tiene que estar en POSICIÓN DE COMANDO, no dentro de un argumento.
# Sin esto, `grep -r 'shutdown' ./logs` se bloquea y el guard se vuelve inusable.
CMD = r"(?:^|[;&|]\s*|\$\(\s*|`\s*|\bsudo\s+|\bdoas\s+|\bnohup\s+|\bexec\s+)"

# `rm -rf X`, `rm -r -f X`, `rm -fr X`: al menos un grupo de flags con r/R.
RM_R = r"rm(?:\s+-[a-zA-Z]+)*\s+-[a-zA-Z]*[rR][a-zA-Z]*(?:\s+-[a-zA-Z]+)*\s+"

# Raíz, home, o una unidad de Windows entera — nunca una subcarpeta.
ROOT_OR_HOME = (
    r"(/|/\*|~|~/\*|\$HOME/?\*?|\$\{HOME\}/?\*?|%USERPROFILE%|"
    r"\$env:USERPROFILE|[a-zA-Z]:\\?\*?)\s*(?:$|[;&|])"
)


# ── The rules ────────────────────────────────────────────────────────────────
# Ordered by how catastrophic the outcome is. Each pattern is deliberately
# specific: `rm -rf ./build` must keep working, `rm -rf /` must not.
DENY_RULES: tuple[DenyRule, ...] = (
    DenyRule(
        name="recursive-delete-of-root-or-home",
        pattern=_rx(CMD + RM_R + ROOT_OR_HOME),
        reason=(
            "Borrado recursivo de la raíz o del home. Si necesitás limpiar algo, "
            "apuntá a una subcarpeta concreta."
        ),
    ),
    DenyRule(
        name="windows-recursive-delete-of-root-or-home",
        pattern=_rx(
            CMD + r"(?:Remove-Item|rd|rmdir|del)\b[^|;&\n]*"
            r"(?:-Recurse|/s\b)[^|;&\n]*"
            r"(?:\$HOME|\$env:USERPROFILE|%USERPROFILE%|[a-zA-Z]:\\(?:\*|\s|$|\"))"
        ),
        reason=(
            "Borrado recursivo de la raíz o del perfil de usuario en Windows. "
            "Apuntá a una subcarpeta concreta."
        ),
    ),
    DenyRule(
        name="delete-rugol-state",
        # Nothing an agent does should erase the platform's own state.
        pattern=_rx(
            CMD + r"(?:" + RM_R + r"|Remove-Item[^|;&\n]*-Recurse[^|;&\n]*|rd\s+/s[^|;&\n]*)"
            r"[^|;&\n]*[\\/]\.rugol\b"
        ),
        reason=(
            "Eso borra el estado de Rugol (agentes, memorias, base de datos). "
            "Si querés resetear, se hace desde /settings o con `rugol uninstall`."
        ),
    ),
    DenyRule(
        name="disk-format-or-raw-write",
        pattern=_rx(
            CMD + r"(?:mkfs(?:\.\w+)?\b|diskpart\b|Format-Volume\b|Clear-Disk\b"
            r"|format\s+[a-zA-Z]:|dd\b[^|;&\n]*\bof=/dev/[a-z]+)"
        ),
        reason="Formatear o escribir crudo sobre un disco no es una operación de agente.",
    ),
    DenyRule(
        name="power-off-or-reboot",
        # Rugol's whole promise is that the machine keeps serving. An agent
        # rebooting its own host is a self-inflicted outage.
        pattern=_rx(
            CMD + r"(?:shutdown\b|reboot\b|halt\b|poweroff\b|Stop-Computer\b"
            r"|Restart-Computer\b|systemctl\s+(?:reboot|poweroff|halt)\b)"
        ),
        reason=(
            "Apagar o reiniciar la máquina cortaría Rugol y todo lo que tiene "
            "agendado. Si hace falta, lo hace una persona."
        ),
    ),
    DenyRule(
        name="force-push-to-default-branch",
        pattern=_rx(
            CMD + r"git\s+push\b[^|;&\n]*(?:--force(?!-with-lease)|(?<![\w-])-f(?![\w-]))"
            r"[^|;&\n]*\b(?:main|master|origin/main|origin/master)\b"
        ),
        reason=(
            "Force-push a la rama principal reescribe historia compartida. "
            "Usá una rama y un PR, o `--force-with-lease` sobre tu propia rama."
        ),
    ),
    DenyRule(
        # Sin ancla de comando: viene dentro de `psql -c '...'`.
        name="drop-database",
        pattern=_rx(r"\bDROP\s+(?:DATABASE|SCHEMA)\b"),
        reason="Eliminar una base de datos completa requiere una persona.",
    ),
    DenyRule(
        name="fork-bomb",
        pattern=re.compile(r":\(\)\s*\{.*\|.*&.*\}\s*;?\s*:"),
        reason="Eso es una fork bomb.",
    ),
    DenyRule(
        name="world-writable-root-or-home",
        pattern=_rx(CMD + r"chmod\s+(?:-[a-zA-Z]+\s+)*777\s+(?:/|~|\$HOME)\s*(?:$|[;&|])"),
        reason="Dejar la raíz o el home world-writable rompe la seguridad del sistema.",
    ),
    DenyRule(
        name="history-or-credential-wipe",
        pattern=_rx(
            CMD + r"rm\b[^|;&\n]*(?:\.ssh/id_|\.claude/\.credentials|\.aws/credentials)"
        ),
        reason="Borrar credenciales dejaría la máquina sin acceso. No es una tarea de agente.",
    ),
)


@dataclass
class GuardVerdict:
    """`allowed=False` blocks the tool call and sends `reason` back to the model."""

    allowed: bool
    rule: str = ""
    reason: str = ""


def evaluate_bash(command: str, *, extra_rules: tuple[DenyRule, ...] = ()) -> GuardVerdict:
    """Check one shell command against every deny rule."""
    if not command or not command.strip():
        return GuardVerdict(allowed=True)
    for rule in DENY_RULES + tuple(extra_rules):
        if rule.pattern.search(command):
            return GuardVerdict(allowed=False, rule=rule.name, reason=rule.reason)
    return GuardVerdict(allowed=True)


def evaluate_write(path: str, *, freeze_dir: str | None) -> GuardVerdict:
    """`freeze`: while set, writes are confined to one directory tree.

    Useful when an agent is debugging and you want it to stop making
    "drive-by" edits across the repo. Borrowed from gstack's `/freeze`.
    """
    if not freeze_dir or not path:
        return GuardVerdict(allowed=True)
    try:
        target = Path(path).expanduser().resolve()
        allowed_root = Path(freeze_dir).expanduser().resolve()
    except (OSError, ValueError):
        return GuardVerdict(allowed=True)  # unparseable → fail open, don't break the run
    if target == allowed_root or allowed_root in target.parents:
        return GuardVerdict(allowed=True)
    return GuardVerdict(
        allowed=False,
        rule="freeze",
        reason=(
            f"Estás en modo freeze: sólo podés escribir dentro de {allowed_root}. "
            f"El archivo {target} queda afuera."
        ),
    )


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def build_guard_hooks(
    *,
    agent_name: str = "",
    freeze_dir: str | None = None,
    extra_rules: tuple[DenyRule, ...] = (),
) -> dict[str, list[Any]]:
    """The `hooks=` value for ClaudeAgentOptions. Empty dict disables nothing —
    pass the result straight through, or don't pass it at all."""
    from claude_agent_sdk import HookMatcher

    async def bash_guard(input_data, tool_use_id, context):  # noqa: ANN001
        try:
            command = str((input_data.get("tool_input") or {}).get("command") or "")
            verdict = evaluate_bash(command, extra_rules=extra_rules)
            if not verdict.allowed:
                logger.warning(
                    "safety: bloqueado %s para %s — %s | comando: %.200s",
                    verdict.rule, agent_name or "?", verdict.reason, command,
                )
                return _deny(f"[Rugol · freno de seguridad: {verdict.rule}] {verdict.reason}")
        except Exception:
            # Fail open: un bug acá no debe matar la corrida del agente.
            logger.exception("safety: el guard de Bash falló — dejo pasar el comando")
        return {}

    async def write_guard(input_data, tool_use_id, context):  # noqa: ANN001
        try:
            tool_input = input_data.get("tool_input") or {}
            path = str(tool_input.get("file_path") or tool_input.get("path") or "")
            verdict = evaluate_write(path, freeze_dir=freeze_dir)
            if not verdict.allowed:
                logger.warning("safety: freeze bloqueó una escritura en %s", path)
                return _deny(f"[Rugol · freeze] {verdict.reason}")
        except Exception:
            logger.exception("safety: el guard de escritura falló — dejo pasar")
        return {}

    matchers: list[Any] = [HookMatcher(matcher="Bash", hooks=[bash_guard])]
    if freeze_dir:
        matchers.append(HookMatcher(matcher="Write|Edit|NotebookEdit", hooks=[write_guard]))
    return {"PreToolUse": matchers}


def extra_rules_from_settings() -> tuple[DenyRule, ...]:
    """`SAFETY_DENY_EXTRA` → reglas. La usan LOS DOS motores, para que apagar
    algo en una instalación valga igual con Claude y con Codex.

    Una regex inválida se ignora con un log; nunca tumba el arranque.
    """
    from core.config import get_settings

    raw = getattr(get_settings(), "SAFETY_DENY_EXTRA", "") or ""
    rules: list[DenyRule] = []
    for i, chunk in enumerate(raw.split(";;")):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            rules.append(DenyRule(
                name=f"extra-{i + 1}",
                pattern=re.compile(chunk, re.IGNORECASE),
                reason="Bloqueado por una regla propia de esta instalación (SAFETY_DENY_EXTRA).",
            ))
        except re.error as e:
            logger.warning("SAFETY_DENY_EXTRA: regex inválida %r ignorada (%s)", chunk, e)
    return tuple(rules)
