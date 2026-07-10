import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_text(name: str) -> str:
    return (_repo_root() / "scripts" / name).read_text(encoding="utf-8")


def test_readme_uninstall_uses_checkout_scripts() -> None:
    text = (_repo_root() / "README.md").read_text(encoding="utf-8")

    assert "./scripts/uninstall.sh" in text
    assert ".\\scripts\\uninstall.ps1" in text
    assert "raw.githubusercontent.com" not in text


def _braced_body(text: str, declaration: str) -> str:
    start = text.index(declaration)
    brace_start = text.index("{", start)
    depth = 0

    for index, char in enumerate(text[brace_start:], start=brace_start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start + 1 : index]

    raise AssertionError(f"Unclosed function body for {declaration}")


def _shell_path_with_mock(bin_dir: Path) -> str:
    return f"{bin_dir}:/usr/bin:/bin"


def _path_prepending(path: Path) -> str:
    return os.pathsep.join((str(path), os.environ.get("PATH", "")))


def _path_without_uv(prefix: Path) -> str:
    uv_names = ("uv", "uv.exe", "uv.cmd", "uv.bat")
    entries = [str(prefix)]
    for raw_entry in os.environ.get("PATH", "").split(os.pathsep):
        if not raw_entry:
            continue
        entry = Path(raw_entry)
        if any((entry / name).exists() for name in uv_names):
            continue
        entries.append(raw_entry)
    return os.pathsep.join(entries)


def _write_mock_uv(bin_dir: Path, *, message: str, exit_code: int) -> None:
    if os.name == "nt":
        uv = bin_dir / "uv.cmd"
        uv.write_text(
            f"@echo off\necho {message} 1>&2\nexit /b {exit_code}\n",
            encoding="utf-8",
        )
        return

    uv = bin_dir / "uv"
    uv.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{message}' >&2\nexit {exit_code}\n",
        encoding="utf-8",
    )
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)


def test_uninstall_sh_removes_uv_tool_and_purges_free_codex_home() -> None:
    text = _script_text("uninstall.sh")
    tool_body = _braced_body(text, "uninstall_free_codex()")
    purge_body = _braced_body(text, "purge_free_codex_home()")

    assert "Does not remove uv, Codex" in text
    assert "uv tool uninstall" in tool_body
    assert 'PACKAGE_NAME="free-codex"' in text
    assert "uv not found on PATH; skipping uv tool uninstall." in tool_body
    assert "is_missing_uv_tool_error" in tool_body
    assert "aborting before deleting ~/.free-codex." in tool_body
    assert "rm -rf" in purge_body
    assert ".free-codex" in purge_body
    assert "npm uninstall" not in text
    assert "uv self uninstall" not in text
    assert "uv python uninstall" not in text


def test_uninstall_sh_fails_when_free_codex_commands_are_running() -> None:
    text = _script_text("uninstall.sh")
    guard_body = _braced_body(text, "assert_no_free_codex_processes_running()")
    main = text[text.index('parse_args "$@"') :]

    for command in (
        "free-codex-server",
        "free-codex",
        "free-codex-init",
    ):
        assert command in text

    assert "FREE_CODEX_COMMANDS" in text

    assert "Free Codex is still running" in guard_body
    assert (
        'step "Checking for running Free Codex processes"\nassert_no_free_codex_processes_running'
        in main
    )


def test_uninstall_ps1_removes_uv_tool_and_purges_free_codex_home() -> None:
    text = _script_text("uninstall.ps1")
    tool_body = _braced_body(text, "function Uninstall-FreeCodex")
    purge_body = _braced_body(text, "function Purge-FreeCodexHome")

    assert "Does not remove uv, Codex" in text
    assert "uv tool uninstall" in tool_body
    assert '$PackageName = "free-codex"' in text
    assert "uv not found on PATH; skipping uv tool uninstall." in tool_body
    assert "Test-MissingUvToolError" in tool_body
    assert "aborting before deleting ~/.free-codex." in tool_body
    assert "Remove-Item" in purge_body
    assert purge_body.count("Remove-Item -LiteralPath") == 1
    assert '$FreeCodexHomeDirname = ".free-codex"' in text
    assert "npm uninstall" not in text
    assert "uv self uninstall" not in text
    assert "uv python uninstall" not in text


def test_uninstall_ps1_fails_when_free_codex_commands_are_running() -> None:
    text = _script_text("uninstall.ps1")
    guard_body = _braced_body(text, "function Assert-NoFreeCodexProcessesRunning")

    for command in (
        "free-codex-server",
        "free-codex",
        "free-codex-init",
    ):
        assert command in text

    assert "FreeCodexCommands" in text

    assert "Free Codex is still running" in guard_body
    assert (
        'Write-Step "Checking for running Free Codex processes"\n'
        "Assert-NoFreeCodexProcessesRunning" in text
    )


def test_uninstall_sh_missing_tool_detection_is_narrow() -> None:
    text = _script_text("uninstall.sh")
    detector_body = _braced_body(text, "is_missing_uv_tool_error()")

    assert "not installed" in detector_body
    assert "no tool" in detector_body
    assert "nothing to uninstall" in detector_body
    assert "permission denied" not in detector_body
    assert "locked" not in detector_body


def test_uninstall_ps1_missing_tool_detection_is_narrow() -> None:
    text = _script_text("uninstall.ps1")
    detector_body = _braced_body(text, "function Test-MissingUvToolError")

    assert "not installed" in detector_body
    assert "no tool" in detector_body
    assert "nothing to uninstall" in detector_body
    assert "permission denied" not in detector_body
    assert "locked" not in detector_body


def test_uninstall_sh_generic_uv_failure_does_not_delete_free_codex_home(
    tmp_path: Path,
) -> None:
    sh = shutil.which("sh")
    if sh is None:
        pytest.skip("sh is not available on this platform")

    home = tmp_path / "home"
    free_codex_home = home / ".free-codex"
    bin_dir = home / ".local" / "bin"
    free_codex_home.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'permission denied while removing tool' >&2\n"
        "exit 42\n",
        encoding="utf-8",
    )
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        [sh, str(_repo_root() / "scripts" / "uninstall.sh")],
        cwd=_repo_root(),
        env={**os.environ, "HOME": str(home), "PATH": _shell_path_with_mock(bin_dir)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert free_codex_home.exists()
    assert "failed with exit code 42" in result.stderr
    assert "before deleting ~/.free-codex" in result.stderr


def test_uninstall_sh_missing_tool_still_deletes_free_codex_home(tmp_path: Path) -> None:
    sh = shutil.which("sh")
    if sh is None:
        pytest.skip("sh is not available on this platform")

    home = tmp_path / "home"
    free_codex_home = home / ".free-codex"
    bin_dir = home / ".local" / "bin"
    free_codex_home.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    uv = bin_dir / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'tool free-codex is not installed' >&2\n"
        "exit 2\n",
        encoding="utf-8",
    )
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        [sh, str(_repo_root() / "scripts" / "uninstall.sh")],
        cwd=_repo_root(),
        env={**os.environ, "HOME": str(home), "PATH": _shell_path_with_mock(bin_dir)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert not free_codex_home.exists()


def test_uninstall_sh_missing_uv_still_deletes_free_codex_home(tmp_path: Path) -> None:
    sh = shutil.which("sh")
    if sh is None:
        pytest.skip("sh is not available on this platform")

    home = tmp_path / "home"
    free_codex_home = home / ".free-codex"
    empty_bin = tmp_path / "empty-bin"
    free_codex_home.mkdir(parents=True)
    empty_bin.mkdir()

    result = subprocess.run(
        [sh, str(_repo_root() / "scripts" / "uninstall.sh")],
        cwd=_repo_root(),
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": f"{empty_bin}:/usr/bin:/bin",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert not free_codex_home.exists()
    assert "uv not found on PATH; skipping uv tool uninstall." in result.stdout


def test_uninstall_ps1_generic_uv_failure_does_not_delete_free_codex_home(
    tmp_path: Path,
) -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        pytest.skip("PowerShell is not available on this platform")

    home = tmp_path / "home"
    free_codex_home = home / ".free-codex"
    bin_dir = home / ".local" / "bin"
    free_codex_home.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    _write_mock_uv(
        bin_dir,
        message="permission denied while removing tool",
        exit_code=42,
    )

    result = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(_repo_root() / "scripts" / "uninstall.ps1")],
        cwd=_repo_root(),
        env={
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PATH": _path_prepending(bin_dir),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert free_codex_home.exists()
    assert "failed with exit code 42" in result.stderr
    assert "before deleting ~/.free-codex" in result.stderr


def test_uninstall_ps1_missing_tool_still_deletes_free_codex_home(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        pytest.skip("PowerShell is not available on this platform")

    home = tmp_path / "home"
    free_codex_home = home / ".free-codex"
    bin_dir = home / ".local" / "bin"
    free_codex_home.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    _write_mock_uv(
        bin_dir,
        message="tool free-codex is not installed",
        exit_code=2,
    )

    result = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(_repo_root() / "scripts" / "uninstall.ps1")],
        cwd=_repo_root(),
        env={
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PATH": _path_prepending(bin_dir),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert not free_codex_home.exists()


def test_uninstall_ps1_missing_uv_still_deletes_free_codex_home(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        pytest.skip("PowerShell is not available on this platform")

    home = tmp_path / "home"
    free_codex_home = home / ".free-codex"
    empty_bin = tmp_path / "empty-bin"
    free_codex_home.mkdir(parents=True)
    empty_bin.mkdir()

    result = subprocess.run(
        [pwsh, "-NoProfile", "-File", str(_repo_root() / "scripts" / "uninstall.ps1")],
        cwd=_repo_root(),
        env={
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PATH": _path_without_uv(empty_bin),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert not free_codex_home.exists()
    assert "uv not found on PATH; skipping uv tool uninstall." in result.stdout
