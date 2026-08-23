"""Los frenos tienen que bloquear el desastre y NO estorbar el trabajo real.

La mitad de abajo importa tanto como la de arriba: un guard con falsos
positivos se termina apagando, y entonces no hay guard.
"""
from __future__ import annotations

import pytest

from core.safety import evaluate_bash, evaluate_write
from core.safety.guards import DenyRule as _DenyRule  # re-export check


# ── Lo que DEBE bloquearse ───────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("command", "expected_rule"),
    [
        ("rm -rf /", "recursive-delete-of-root-or-home"),
        ("rm -rf /*", "recursive-delete-of-root-or-home"),
        ("rm -rf ~", "recursive-delete-of-root-or-home"),
        ("rm -rf $HOME", "recursive-delete-of-root-or-home"),
        ("sudo rm -fr /", "recursive-delete-of-root-or-home"),
        ("rm -r -f /", "recursive-delete-of-root-or-home"),
        ("Remove-Item -Recurse -Force $env:USERPROFILE", "windows-recursive-delete-of-root-or-home"),
        ("rd /s /q C:\\", "windows-recursive-delete-of-root-or-home"),
        ("rm -rf ~/.rugol", "delete-rugol-state"),
        ("rm -rf /Users/edu/.rugol/data", "delete-rugol-state"),
        ("mkfs.ext4 /dev/sda1", "disk-format-or-raw-write"),
        ("dd if=/dev/zero of=/dev/sda bs=1M", "disk-format-or-raw-write"),
        ("format C:", "disk-format-or-raw-write"),
        ("sudo shutdown -h now", "power-off-or-reboot"),
        ("Restart-Computer -Force", "power-off-or-reboot"),
        ("systemctl reboot", "power-off-or-reboot"),
        ("git push --force origin main", "force-push-to-default-branch"),
        ("git push -f origin master", "force-push-to-default-branch"),
        ("psql -c 'DROP DATABASE produccion'", "drop-database"),
        (":(){ :|:& };:", "fork-bomb"),
        ("chmod -R 777 /", "world-writable-root-or-home"),
        ("rm ~/.ssh/id_rsa", "history-or-credential-wipe"),
        ("rm -f ~/.claude/.credentials.json", "history-or-credential-wipe"),
    ],
)
def test_blocks_the_catastrophic(command, expected_rule):
    verdict = evaluate_bash(command)
    assert not verdict.allowed, f"debería bloquear: {command}"
    assert verdict.rule == expected_rule
    assert verdict.reason, "un bloqueo sin explicación hace que el modelo reintente igual"


# ── Lo que NO debe estorbar ──────────────────────────────────────────────────
@pytest.mark.parametrize(
    "command",
    [
        # Limpieza normal de proyecto
        "rm -rf node_modules",
        "rm -rf ./build ./dist",
        "rm -rf .next/cache",
        "rm -rf /tmp/rugol-test",
        "Remove-Item -Recurse -Force .\\dist",
        "rm -rf $HOME/proyectos/viejo",          # bajo el home, no EL home
        "rm -rf ~/Downloads/basura",
        # git normal
        "git push origin main",
        "git push --force-with-lease origin mi-rama",
        "git push --force origin mi-rama-de-trabajo",
        "git reset --hard origin/main",
        # SQL normal
        "psql -c 'DROP TABLE staging_tmp'",
        "psql -c 'DELETE FROM eventos WHERE fecha < now()'",
        # Cosas que sólo se parecen
        "echo 'no corras rm -rf / nunca'",
        "grep -r 'shutdown' ./logs",
        "python manage.py collectstatic",
        "dd if=backup.img of=./restore.img",
        "chmod -R 755 ./scripts",
        "curl -s https://api.example.com | jq .",
        "uv pip install -r core/requirements.txt",
        "npm run build",
    ],
)
def test_lets_real_work_through(command):
    verdict = evaluate_bash(command)
    assert verdict.allowed, f"falso positivo en: {command} (regla {verdict.rule})"


def test_empty_command_is_allowed():
    assert evaluate_bash("").allowed
    assert evaluate_bash("   ").allowed


def test_extra_rules_are_honoured():
    import re
    extra = (_DenyRule(name="sin-terraform", pattern=re.compile(r"terraform\s+destroy"),
                       reason="no en producción"),)
    assert evaluate_bash("terraform destroy -auto-approve").allowed is True  # sin extra
    v = evaluate_bash("terraform destroy -auto-approve", extra_rules=extra)
    assert not v.allowed and v.rule == "sin-terraform"


# ── freeze ───────────────────────────────────────────────────────────────────
def test_freeze_confines_writes(tmp_path):
    allowed_dir = tmp_path / "modulo"
    allowed_dir.mkdir()
    inside = allowed_dir / "a.py"
    outside = tmp_path / "otro" / "b.py"

    assert evaluate_write(str(inside), freeze_dir=str(allowed_dir)).allowed
    assert evaluate_write(str(allowed_dir / "sub" / "c.py"), freeze_dir=str(allowed_dir)).allowed

    v = evaluate_write(str(outside), freeze_dir=str(allowed_dir))
    assert not v.allowed and v.rule == "freeze"
    assert str(allowed_dir) in v.reason, "el mensaje debe decir dónde SÍ puede escribir"


def test_freeze_off_by_default(tmp_path):
    assert evaluate_write(str(tmp_path / "cualquiera.py"), freeze_dir=None).allowed


def test_freeze_fails_open_on_garbage():
    # Una ruta imposible no debe tumbar la corrida.
    assert evaluate_write("\x00no-es-una-ruta", freeze_dir="/tmp").allowed


# ── El hook, extremo a extremo ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hook_denies_with_a_reason_the_model_can_read():
    from core.safety import build_guard_hooks

    hooks = build_guard_hooks(agent_name="tester")
    matcher = hooks["PreToolUse"][0]
    assert matcher.matcher == "Bash"
    guard = matcher.hooks[0]

    out = await guard({"tool_input": {"command": "rm -rf /"}}, "tu_1", {"signal": None})
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["hookEventName"] == "PreToolUse"
    assert "Rugol" in hso["permissionDecisionReason"]

    ok = await guard({"tool_input": {"command": "ls -la"}}, "tu_2", {"signal": None})
    assert ok == {}, "un comando normal no debe devolver decisión"


@pytest.mark.asyncio
async def test_hook_never_raises_on_malformed_input():
    """Un bug del guard no puede matar la corrida del agente."""
    from core.safety import build_guard_hooks

    guard = build_guard_hooks()["PreToolUse"][0].hooks[0]
    for bad in ({}, {"tool_input": None}, {"tool_input": {"command": None}}, {"otra": "cosa"}):
        assert await guard(bad, None, {"signal": None}) == {}


@pytest.mark.asyncio
async def test_freeze_matcher_only_appears_when_frozen():
    from core.safety import build_guard_hooks

    assert len(build_guard_hooks()["PreToolUse"]) == 1
    frozen = build_guard_hooks(freeze_dir="/tmp/x")["PreToolUse"]
    assert len(frozen) == 2
    assert "Write" in frozen[1].matcher
