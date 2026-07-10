import os
import shutil
from pathlib import Path

import pytest
from free_codex.cli.launchers.codex import codex_config_args

from smoke.lib.child_process import (
    cmd_free_codex_init,
    cmd_free_codex_serve,
    run_captured_text,
)
from smoke.lib.config import SmokeConfig
from smoke.lib.server import start_server
from smoke.lib.skips import skip_upstream_unavailable

pytestmark = [pytest.mark.live, pytest.mark.smoke_target("cli")]


def test_free_codex_init_scaffolds_user_config(
    smoke_config: SmokeConfig, tmp_path: Path
) -> None:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    result = run_captured_text(
        cmd_free_codex_init(),
        cwd=smoke_config.root,
        env=env,
        timeout=smoke_config.timeout_s,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / ".free-codex" / ".env").is_file()


def test_free_codex_entrypoint_starts_server(smoke_config: SmokeConfig) -> None:
    with start_server(
        smoke_config,
        command=cmd_free_codex_serve(),
        env_overrides={"MESSAGING_PLATFORM": "none"},
        name="entrypoint",
    ) as server:
        assert server.process.poll() is None


def test_codex_cli_prompt_when_available(
    smoke_config: SmokeConfig, tmp_path: Path
) -> None:
    codex_bin = shutil.which(smoke_config.codex_bin)
    if not codex_bin:
        pytest.skip(f"Codex CLI not found: {smoke_config.codex_bin}")
    models = smoke_config.provider_models()
    if not models:
        pytest.skip("no configured provider model available for Codex CLI smoke")

    with start_server(
        smoke_config,
        env_overrides={"MODEL": models[0].full_model, "MESSAGING_PLATFORM": "none"},
        name="codex-cli",
    ) as server:
        env = os.environ.copy()
        env["FREE_CODEX_API_KEY"] = smoke_config.settings.free_codex_auth_token
        provider_args = codex_config_args(
            api_url=server.base_url, model=models[0].full_model
        )
        if smoke_config.settings.free_codex_auth_token:
            env["FREE_CODEX_AUTH_TOKEN"] = smoke_config.settings.free_codex_auth_token
        else:
            env.pop("FREE_CODEX_AUTH_TOKEN", None)
        result = run_captured_text(
            [
                codex_bin,
                *provider_args,
                "exec",
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "--skip-git-repo-check",
                "Reply with exactly FREE_CODEX_SMOKE_PONG",
            ],
            cwd=tmp_path,
            env=env,
            timeout=smoke_config.timeout_s,
            check=False,
        )
        server_log = server.log_path.read_text(encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "POST /v1/responses" in server_log, (
        "Codex CLI did not call the local Responses-compatible endpoint"
    )
    if "FREE_CODEX_SMOKE_PONG" not in result.stdout:
        skip_upstream_unavailable(
            "Codex CLI reached the local proxy but returned no smoke token"
        )
