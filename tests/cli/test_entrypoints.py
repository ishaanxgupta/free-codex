"""Tests for cli/entrypoints.py — free-codex-init scaffolding logic."""

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import Request

import pytest

from free_codex.config.settings import Settings


def _launcher_settings(
    *,
    port: int = 8082,
    token: str = "free-codex",
) -> Settings:
    return Settings.model_construct(
        host="0.0.0.0",
        port=port,
        free_codex_auth_token=token,
        model="nvidia_nim/test-model",
    )


def _run_init(tmp_home: Path) -> tuple[str, Path]:
    """Run init() with home directory redirected to tmp_home. Returns (printed output, env_file path)."""
    from free_codex.cli.entrypoints import init

    env_file = tmp_home / ".free-codex" / ".env"
    printed: list[str] = []

    with (
        patch("pathlib.Path.home", return_value=tmp_home),
        patch(
            "builtins.print",
            side_effect=lambda *a: printed.append(" ".join(str(x) for x in a)),
        ),
    ):
        init()

    return "\n".join(printed), env_file


class _JsonResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _JsonResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_init_creates_env_file(tmp_path: Path) -> None:
    """init() creates .env from the bundled template when it doesn't exist yet."""
    output, env_file = _run_init(tmp_path)

    assert env_file.exists()
    assert env_file.stat().st_size > 0
    assert str(env_file) in output


def test_init_copies_template_content(tmp_path: Path) -> None:
    """init() writes the canonical root env.example content, not an empty file."""
    template = (Path(__file__).resolve().parents[2] / ".env.example").read_text(
        encoding="utf-8"
    )
    _, env_file = _run_init(tmp_path)

    assert env_file.read_text("utf-8") == template


def test_init_migrates_home_checkout_env_before_template(tmp_path: Path) -> None:
    """init() preserves users who kept config in ~/free-codex/.env."""
    legacy_env = tmp_path / "free-codex" / ".env"
    legacy_env.parent.mkdir(parents=True)
    legacy_env.write_text("MODEL=deepseek/deepseek-chat\n", encoding="utf-8")

    output, env_file = _run_init(tmp_path)

    assert env_file.read_text("utf-8") == "MODEL=deepseek/deepseek-chat\n"
    assert f"Config migrated from {legacy_env}" in output


def test_init_migrates_legacy_xdg_env_before_template(tmp_path: Path) -> None:
    """init() preserves users who kept config in ~/.config/free-codex/.env."""
    legacy_env = tmp_path / ".config" / "free-codex" / ".env"
    legacy_env.parent.mkdir(parents=True)
    legacy_env.write_text("MODEL=open_router/free-model\n", encoding="utf-8")

    output, env_file = _run_init(tmp_path)

    assert env_file.read_text("utf-8") == "MODEL=open_router/free-model\n"
    assert f"Config migrated from {legacy_env}" in output


def test_legacy_env_migration_does_not_overwrite_managed_env(
    tmp_path: Path,
) -> None:
    """Legacy migration never overwrites an existing ~/.free-codex/.env."""
    from free_codex.cli.entrypoints import _migrate_legacy_env_if_missing

    managed_env = tmp_path / ".free-codex" / ".env"
    managed_env.parent.mkdir(parents=True)
    managed_env.write_text("MODEL=nvidia_nim/current\n", encoding="utf-8")
    legacy_env = tmp_path / "free-codex" / ".env"
    legacy_env.parent.mkdir(parents=True)
    legacy_env.write_text("MODEL=deepseek/legacy\n", encoding="utf-8")

    with patch("pathlib.Path.home", return_value=tmp_path):
        migrated_from = _migrate_legacy_env_if_missing()

    assert migrated_from is None
    assert managed_env.read_text("utf-8") == "MODEL=nvidia_nim/current\n"


def test_env_template_loader_uses_root_template_in_source_checkout() -> None:
    """Source checkout fallback uses the root .env.example as the single source."""
    from free_codex.config.env_template import load_env_template

    template = (Path(__file__).resolve().parents[2] / ".env.example").read_text(
        encoding="utf-8"
    )

    assert load_env_template() == template


def test_init_creates_parent_directories(tmp_path: Path) -> None:
    """init() creates ~/.free-codex/ even if it doesn't exist."""
    config_dir = tmp_path / ".free-codex"
    assert not config_dir.exists()

    _run_init(tmp_path)

    assert config_dir.is_dir()


def test_init_skips_if_env_already_exists(tmp_path: Path) -> None:
    """init() does not overwrite an existing .env and prints a warning."""
    # Create it first
    _run_init(tmp_path)

    env_file = tmp_path / ".free-codex" / ".env"
    env_file.write_text("existing content", encoding="utf-8")

    output, _ = _run_init(tmp_path)

    assert env_file.read_text("utf-8") == "existing content"
    assert "already exists" in output


def test_init_prints_next_step_hint(tmp_path: Path) -> None:
    """init() tells the user to run free-codex-server after editing .env."""
    output, _ = _run_init(tmp_path)

    assert "free-codex-server" in output


def test_cli_scripts_are_registered() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )

    scripts = pyproject["project"]["scripts"]
    assert scripts["free-codex-server"] == "free_codex.cli.entrypoints:serve"
    assert scripts["free-codex-init"] == "free_codex.cli.entrypoints:init"
    assert scripts["free-codex"] == "free_codex.cli.launchers.codex:launch"


def test_schedule_open_admin_browser_opens_when_health_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening /admin runs after /health preflight succeeds."""
    monkeypatch.delenv("FREE_CODEX_OPEN_BROWSER", raising=False)
    from free_codex.api.admin_urls import local_admin_url
    from free_codex.cli import entrypoints

    settings = _launcher_settings(port=31337)
    opened_urls: list[str] = []

    class ImmediateThread:
        def __init__(self, target=None, **_kwargs: object) -> None:
            self._target = target

        def start(self) -> None:
            assert self._target is not None
            self._target()

    with (
        patch.object(entrypoints.threading, "Thread", ImmediateThread),
        patch.object(entrypoints, "preflight_proxy", return_value=None),
        patch.object(
            entrypoints.webbrowser,
            "open",
            side_effect=lambda url: opened_urls.append(url),
        ),
        patch.object(entrypoints.time, "sleep"),
    ):
        entrypoints._schedule_open_admin_browser(settings)

    assert opened_urls == [local_admin_url(settings)]


def test_schedule_open_admin_browser_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FREE_CODEX_OPEN_BROWSER", "0")
    from free_codex.cli import entrypoints

    settings = _launcher_settings()

    with patch.object(entrypoints.threading, "Thread") as thread_cls:
        entrypoints._schedule_open_admin_browser(settings)

    thread_cls.assert_not_called()


def test_serve_supervisor_restarts_when_app_requests_restart() -> None:
    from free_codex.cli import entrypoints

    settings = _launcher_settings()
    get_settings = MagicMock(side_effect=[settings, settings])
    get_settings.cache_clear = MagicMock()
    servers: list[object] = []

    class FakeServer:
        def __init__(self, config):
            self.config = config
            self.should_exit = False
            servers.append(self)

        def run(self):
            if len(servers) == 1:
                self.config.app.app.state.admin_restart_callback()
                assert self.should_exit is True

    def fake_config(app, **kwargs):
        return SimpleNamespace(app=app, kwargs=kwargs)

    with (
        patch.object(entrypoints, "get_settings", get_settings),
        patch.object(entrypoints.uvicorn, "Config", side_effect=fake_config),
        patch.object(entrypoints.uvicorn, "Server", side_effect=FakeServer),
        patch.object(entrypoints, "_schedule_open_admin_browser"),
        patch.object(entrypoints, "kill_all_best_effort") as kill_all,
    ):
        entrypoints.serve()

    assert len(servers) == 2
    get_settings.cache_clear.assert_called_once()
    kill_all.assert_called_once()


def test_serve_migrates_legacy_env_before_loading_settings(tmp_path: Path) -> None:
    from free_codex.cli import entrypoints

    legacy_env = tmp_path / "free-codex" / ".env"
    legacy_env.parent.mkdir(parents=True)
    legacy_env.write_text("MODEL=deepseek/deepseek-chat\n", encoding="utf-8")
    settings = _launcher_settings()
    get_settings = MagicMock(return_value=settings)
    get_settings.cache_clear = MagicMock()

    with (
        patch("pathlib.Path.home", return_value=tmp_path),
        patch.object(entrypoints, "get_settings", get_settings),
        patch.object(entrypoints, "_run_supervised_server", return_value=False),
        patch.object(entrypoints, "kill_all_best_effort"),
    ):
        entrypoints.serve()

    assert (tmp_path / ".free-codex" / ".env").read_text("utf-8") == (
        "MODEL=deepseek/deepseek-chat\n"
    )
    get_settings.assert_called_once_with()


def test_serve_migrates_hf_token_before_loading_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from free_codex.cli import entrypoints

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("HF_TOKEN=legacy-hf\n", encoding="utf-8")
    settings = _launcher_settings()
    get_settings = MagicMock(return_value=settings)
    get_settings.cache_clear = MagicMock()
    monkeypatch.chdir(repo)

    with (
        patch("pathlib.Path.home", return_value=tmp_path),
        patch.object(entrypoints, "get_settings", get_settings),
        patch.object(entrypoints, "_run_supervised_server", return_value=False),
        patch.object(entrypoints, "kill_all_best_effort"),
        patch.object(entrypoints, "explicit_env_file_huggingface_warning"),
    ):
        entrypoints.serve()

    assert (repo / ".env").read_text(encoding="utf-8") == (
        "HUGGINGFACE_API_KEY=legacy-hf\n"
    )
    get_settings.assert_called_once_with()


def test_config_env_key_migration_warns_for_explicit_env_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from free_codex.cli import entrypoints

    explicit = tmp_path / "custom.env"
    explicit.write_text("HF_TOKEN=legacy-hf\n", encoding="utf-8")

    with patch.dict(entrypoints.os.environ, {"FREE_CODEX_ENV_FILE": str(explicit)}):
        migrated = entrypoints._migrate_config_env_keys()

    assert migrated == ()
    assert "HF_TOKEN" in capsys.readouterr().err
    assert explicit.read_text(encoding="utf-8") == "HF_TOKEN=legacy-hf\n"


def test_serve_handles_keyboard_interrupt_without_traceback() -> None:
    from free_codex.cli import entrypoints

    settings = _launcher_settings()
    get_settings = MagicMock(return_value=settings)
    get_settings.cache_clear = MagicMock()

    with (
        patch.object(entrypoints, "get_settings", get_settings),
        patch.object(
            entrypoints,
            "_run_supervised_server",
            side_effect=KeyboardInterrupt,
        ),
        patch.object(entrypoints, "kill_all_best_effort") as kill_all,
    ):
        entrypoints.serve()

    get_settings.cache_clear.assert_not_called()
    kill_all.assert_called_once()


def test_launch_codex_passes_responses_config_and_child_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from free_codex.cli.launchers.codex import launch

    monkeypatch.setenv("OPENAI_API_KEY", "official-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("CODEX_HOME", "keep-home")
    settings = _launcher_settings(port=9191, token="proxy-token")
    catalog_path = tmp_path / "codex-model-catalog.json"
    requests: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> _JsonResponse:
        requests.append(request)
        assert timeout == 1.5
        return _JsonResponse(
            {
                "data": [
                    {
                        "id": "anthropic/nvidia_nim/provider-model",
                        "display_name": "NVIDIA model",
                    },
                    {
                        "id": ("claude-3-free-codex-no-thinking/nvidia_nim/provider-model"),
                        "display_name": "NVIDIA model (no thinking)",
                    },
                    {
                        "id": "claude-opus-4-20250514",
                        "display_name": "Claude Opus 4",
                    },
                ]
            }
        )

    with (
        patch(
            "free_codex.cli.launchers.codex.get_settings", return_value=settings
        ),
        patch(
            "free_codex.cli.launchers.codex.preflight_proxy", return_value=None
        ),
        patch(
            "free_codex.cli.launchers.common.shutil.which",
            return_value="resolved-codex.cmd",
        ),
        patch(
            "free_codex.cli.launchers.codex.codex_model_catalog_path",
            return_value=catalog_path,
        ),
        patch("free_codex.cli.launchers.codex.urlopen", side_effect=fake_urlopen),
        patch("free_codex.cli.launchers.common.subprocess.Popen") as popen,
        patch("free_codex.cli.launchers.common.register_pid") as register_pid,
        patch("free_codex.cli.launchers.common.unregister_pid") as unregister_pid,
        pytest.raises(SystemExit) as exc_info,
    ):
        process = popen.return_value
        process.pid = 12345
        process.wait.return_value = 0
        launch(["exec", "hello"])

    assert exc_info.value.code == 0
    command = popen.call_args.args[0]
    assert command[0] == "resolved-codex.cmd"
    assert 'model_provider="free_codex"' in command
    assert 'model_providers.free_codex.base_url="http://127.0.0.1:9191/v1"' in command
    assert 'model_providers.free_codex.wire_api="responses"' in command
    assert f"model_catalog_json={json.dumps(str(catalog_path))}" in command
    assert command[-2:] == ["exec", "hello"]
    assert len(requests) == 1
    request = requests[0]
    assert request.full_url == "http://127.0.0.1:9191/v1/models"
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["x-api-key"] == "proxy-token"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert [model["slug"] for model in catalog["models"]] == [
        "nvidia_nim/provider-model"
    ]
    child_env = popen.call_args.kwargs["env"]
    assert child_env["FREE_CODEX_API_KEY"] == "proxy-token"
    assert child_env["CODEX_HOME"] == "keep-home"
    assert "OPENAI_API_KEY" not in child_env
    assert "OPENAI_BASE_URL" not in child_env
    register_pid.assert_called_once_with(12345)
    unregister_pid.assert_called_once_with(12345)


def test_launch_codex_catalog_failure_warns_and_continues(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    from free_codex.cli.launchers.codex import launch

    settings = _launcher_settings(port=9191, token="proxy-token")

    with (
        patch(
            "free_codex.cli.launchers.codex.get_settings", return_value=settings
        ),
        patch(
            "free_codex.cli.launchers.codex.preflight_proxy", return_value=None
        ),
        patch(
            "free_codex.cli.launchers.common.shutil.which",
            return_value="resolved-codex.cmd",
        ),
        patch(
            "free_codex.cli.launchers.codex.codex_model_catalog_path",
            return_value=tmp_path / "codex-model-catalog.json",
        ),
        patch(
            "free_codex.cli.launchers.codex.urlopen", side_effect=URLError("boom")
        ),
        patch("free_codex.cli.launchers.common.subprocess.Popen") as popen,
        patch("free_codex.cli.launchers.common.register_pid"),
        patch("free_codex.cli.launchers.common.unregister_pid"),
        pytest.raises(SystemExit) as exc_info,
    ):
        process = popen.return_value
        process.pid = 12345
        process.wait.return_value = 0
        launch(["exec", "hello"])

    assert exc_info.value.code == 0
    command = popen.call_args.args[0]
    assert not any("model_catalog_json=" in arg for arg in command)
    captured = capsys.readouterr()
    assert "could not prepare Codex model catalog" in captured.err
    assert "launching without model picker catalog" in captured.err
