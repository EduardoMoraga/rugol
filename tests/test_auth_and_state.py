"""Auth resolution + where mutable state lives.

Both were real production failures on the Windows box, and both were invisible:
`doctor` grepped the `.env` for a token instead of asking the CLI, and
`settings.json` / the scheduler jobstore lived inside the app directory, which a
reinstall deletes. These tests pin the fixed behaviour.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys

import pytest

from core import runtime_state
from core.config import REPO_ROOT, adopt_legacy_data, data_dir
from core.runner import claude_cli


def _load_auth_cli():
    """cli/rugol-auth.py — hyphenated on purpose (it's a command, not a module)."""
    path = REPO_ROOT / "cli" / "rugol-auth.py"
    spec = importlib.util.spec_from_file_location("rugol_auth_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------- CLI resolution ----------

def test_find_cli_prefers_the_bundled_binary():
    """The SDK runs its own bundled CLI, so that is the one whose login matters.

    Reporting the PATH `claude` here is how you end up debugging the wrong
    binary — they can be different versions with different credentials.
    """
    cli_path, source = claude_cli.find_cli()
    assert cli_path, "claude-agent-sdk should ship a CLI binary"
    assert source == "bundled"
    assert "claude_agent_sdk" in cli_path


# ---------- auth_status ----------

def _fake_status_run(payload: dict, monkeypatch):
    class Proc:
        stdout = json.dumps(payload)
        stderr = ""
        returncode = 0

    def fake_run(cmd, **kwargs):
        # `--version` goes through the same subprocess helper.
        if "--version" in cmd:
            class V:
                stdout = "9.9.9 (Claude Code)"
                stderr = ""
            return V()
        return Proc()

    monkeypatch.setattr(claude_cli.subprocess, "run", fake_run)


@pytest.mark.parametrize(
    ("auth_method", "expected_source"),
    [
        ("oauth_token", "env-token"),
        ("api_key", "api-key"),
        ("claude.ai", "machine-login"),
    ],
)
def test_auth_status_trusts_the_cli_over_our_env_guess(auth_method, expected_source, monkeypatch):
    """`authMethod` is the authority on which credential actually won.

    Guessing from the environment gets the precedence backwards: a stored login
    beats an env ANTHROPIC_API_KEY, while an env oauth token beats the login.
    """
    _fake_status_run({"loggedIn": True, "authMethod": auth_method, "email": "a@b.c"}, monkeypatch)
    # Env deliberately contradicts the CLI's answer.
    status = claude_cli.auth_status(env={"ANTHROPIC_API_KEY": "sk-ant-whatever"})
    assert status["credential_source"] == expected_source
    assert status["logged_in"] is True


def test_auth_status_reports_not_logged_in_with_a_reason(monkeypatch):
    _fake_status_run({"loggedIn": False, "authMethod": "none"}, monkeypatch)
    status = claude_cli.auth_status(env={})
    assert status["logged_in"] is False
    assert status["error"], "a failed check must carry something the user can read"


def test_auth_status_never_raises_when_the_cli_is_missing(monkeypatch):
    """This feeds a health endpoint that must answer precisely when auth is broken."""
    monkeypatch.setattr(claude_cli, "find_cli", lambda: (None, "none"))
    status = claude_cli.auth_status(env={})
    assert status["logged_in"] is False
    assert "rugol update" in status["error"]


def test_verify_credentials_reports_the_api_rejection(monkeypatch):
    """A revoked token passes `auth status`; only a real call catches it."""
    class Proc:
        stdout = json.dumps({
            "type": "result", "subtype": "success", "is_error": True,
            "api_error_status": 401,
            "result": "Failed to authenticate. API Error: 401 OAuth access token is invalid.",
        })
        stderr = ""
        returncode = 0

    monkeypatch.setattr(claude_cli.subprocess, "run", lambda cmd, **kw: Proc())
    probe = claude_cli.verify_credentials(env={})
    assert probe["verified"] is False
    assert probe["verify_status"] == 401
    assert "401" in probe["verify_error"]


# ---------- .env surgery ----------

def test_login_edits_only_the_auth_keys(tmp_path):
    """`rugol login` must not be `rugol setup`.

    Rewriting the whole file is what forced the user to re-enter model, Telegram
    token and default agent just to fix a credential.
    """
    auth_cli = _load_auth_cli()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Generado por rugol setup\n"
        "USE_SUBSCRIPTION=true\n"
        "CLAUDE_CODE_OAUTH_TOKEN=token-vencido\n"
        "DEFAULT_MODEL=claude-sonnet-5\n"
        "\n"
        "# Telegram\n"
        "TELEGRAM_BOT_TOKEN=123:abc\n",
        encoding="utf-8",
    )

    auth_cli.set_env_keys({"CLAUDE_CODE_OAUTH_TOKEN": "", "SESSION_SECRET": "nuevo"}, path=env_file)
    text = env_file.read_text(encoding="utf-8")

    assert "CLAUDE_CODE_OAUTH_TOKEN=\n" in text          # cleared, not deleted
    assert "TELEGRAM_BOT_TOKEN=123:abc" in text          # untouched
    assert "DEFAULT_MODEL=claude-sonnet-5" in text       # untouched
    assert "# Generado por rugol setup" in text          # comments survive
    assert "# Telegram" in text
    assert "SESSION_SECRET=nuevo" in text                # new key appended


def test_run_env_from_file_mirrors_the_runner(tmp_path, monkeypatch):
    """The CLI must report the same credential the core would hand a run."""
    auth_cli = _load_auth_cli()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "USE_SUBSCRIPTION=true\nCLAUDE_CODE_OAUTH_TOKEN=tok\nANTHROPIC_API_KEY=sk-ant-x\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(auth_cli, "ENV_FILE", env_file)
    env = auth_cli.run_env_from_file()
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert "ANTHROPIC_API_KEY" not in env, "subscription mode must not leak an API key"

    env_file.write_text("USE_SUBSCRIPTION=false\nANTHROPIC_API_KEY=sk-ant-x\n", encoding="utf-8")
    env = auth_cli.run_env_from_file()
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-x"
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env


# ---------- state location ----------

def test_data_dir_follows_the_override(tmp_path, monkeypatch):
    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "state"))
    assert data_dir() == tmp_path / "state"
    assert data_dir().is_dir(), "callers assume it exists"


def test_settings_live_outside_the_app_dir(tmp_path, monkeypatch):
    """A reinstall deletes the app directory; tokens must not be in there."""
    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(runtime_state, "_cached", None)
    assert runtime_state.settings_path().parent == tmp_path / "state"

    runtime_state.save({"telegram_bot_token": "123:abc"})
    written = tmp_path / "state" / "settings.json"
    assert written.is_file()
    assert json.loads(written.read_text())["telegram_bot_token"] == "123:abc"


def test_adopt_legacy_data_copies_once_and_never_clobbers(tmp_path, monkeypatch):
    legacy = REPO_ROOT / "data"
    legacy.mkdir(parents=True, exist_ok=True)
    marker = legacy / "adopt-probe.json"
    marker.write_text('{"from": "legacy"}', encoding="utf-8")
    try:
        target = tmp_path / "state"
        monkeypatch.setenv("RUGOL_DATA_DIR", str(target))

        assert adopt_legacy_data(("adopt-probe.json",)) == ["adopt-probe.json"]
        assert json.loads((target / "adopt-probe.json").read_text())["from"] == "legacy"
        assert marker.exists(), "the legacy file stays as a backup"

        # Second run is a no-op — current state must win over the old copy.
        (target / "adopt-probe.json").write_text('{"from": "current"}', encoding="utf-8")
        assert adopt_legacy_data(("adopt-probe.json",)) == []
        assert json.loads((target / "adopt-probe.json").read_text())["from"] == "current"
    finally:
        marker.unlink(missing_ok=True)


def test_adopt_is_a_noop_when_data_dir_is_the_repo(monkeypatch):
    monkeypatch.delenv("RUGOL_DATA_DIR", raising=False)
    assert adopt_legacy_data() == []


# ---------- model catalogue ----------

def test_offered_models_are_all_accepted_by_the_api():
    """The Windows wizard once offered a model the API's whitelist rejected."""
    from core.api.agents import ALLOWED_MODELS
    from core.llm_models import MODEL_CHOICES

    for value, _label in MODEL_CHOICES:
        assert value in ALLOWED_MODELS, f"{value} is offered but not accepted"


def test_legacy_models_still_save():
    """Agents written by earlier versions keep their model on edit."""
    from core.api.agents import ALLOWED_MODELS

    for legacy in ("claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"):
        assert legacy in ALLOWED_MODELS


def test_wizards_and_catalogue_agree():
    """Both setup wizards write a model the API accepts."""
    from core.llm_models import ALLOWED_MODELS

    for cli_file in ("cli/rugol", "cli/rugol.ps1"):
        text = (REPO_ROOT / cli_file).read_text(encoding="utf-8")
        offered = set(re.findall(r'"(claude-[a-z0-9.-]+)"', text))
        assert offered, f"{cli_file} should offer at least one model"
        for model in offered:
            assert model in ALLOWED_MODELS, f"{cli_file} offers {model}, not in ALLOWED_MODELS"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))


# ── Cambiar de modelo tiene que funcionar ────────────────────────────────────
# Regresión: la detección de cambios del registry no miraba `model`, así que
# cambiar el modelo de un agente reescribía el .md y la base seguía con el
# viejo. El runner usa la base → cambiar de modelo no hacía nada.

@pytest.mark.asyncio
async def test_changing_the_model_reaches_the_database(tmp_path, monkeypatch):
    from sqlalchemy import select

    from core import runtime_state
    from core.db import async_session_factory, init_db
    from core.db.models import Agent
    from core.registry.service import upsert_agent_file

    monkeypatch.setattr(runtime_state, "default_model", lambda: "claude-sonnet-5")
    await init_db()

    md = tmp_path / "modelo-test.md"

    def write(model: str, body: str = "Cuerpo estable.") -> None:
        md.write_text(
            f"---\nname: modelo-test\nmodel: {model}\ndescription: prueba\n---\n\n{body}\n",
            encoding="utf-8",
        )

    async def model_in_db() -> str:
        async with async_session_factory() as s:
            row = (await s.execute(
                select(Agent).where(Agent.name == "modelo-test")
            )).scalar_one()
            return row.model

    try:
        write("claude-sonnet-5")
        await upsert_agent_file(md)
        assert await model_in_db() == "claude-sonnet-5"

        # SOLO cambia el modelo: el cuerpo queda idéntico, así que el hash no
        # cambia. Ahí es donde se rompía.
        write("claude-opus-5")
        await upsert_agent_file(md)
        assert await model_in_db() == "claude-opus-5", (
            "cambiar sólo el modelo tiene que llegar a la base; si no, el "
            "runner sigue usando el viejo"
        )

        # Y la descripción, por lo mismo.
        md.write_text(
            "---\nname: modelo-test\nmodel: claude-opus-5\ndescription: nueva\n---\n\n"
            "Cuerpo estable.\n", encoding="utf-8",
        )
        await upsert_agent_file(md)
        async with async_session_factory() as s:
            row = (await s.execute(
                select(Agent).where(Agent.name == "modelo-test")
            )).scalar_one()
            assert row.description == "nueva"
    finally:
        async with async_session_factory() as s:
            for a in (await s.execute(
                select(Agent).where(Agent.name == "modelo-test")
            )).scalars():
                await s.delete(a)
            await s.commit()
