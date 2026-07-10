"""Managed Codex task command, environment, and JSONL parsing."""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from free_codex.cli.launchers.codex import (
    build_codex_launcher_env,
    codex_config_args,
)

CODEX_BINARY_NAME = "codex"


@dataclass(frozen=True, slots=True)
class ManagedCodexTaskRequest:
    """One prompt execution request for a managed Codex subprocess."""

    prompt: str
    session_id: str | None = None
    fork_session: bool = False


@dataclass(frozen=True, slots=True)
class ManagedCodexInvocation:
    """Concrete subprocess invocation assembled for a managed Codex task."""

    argv: tuple[str, ...]
    env: dict[str, str]
    cwd: str
    trace_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ManagedCodexConfig:
    """Configuration for a managed Codex subprocess."""

    workspace_path: str
    api_url: str
    model: str | None = None
    allowed_dirs: list[str] = field(default_factory=list)
    plans_directory: str | None = None
    codex_bin: str = CODEX_BINARY_NAME
    auth_token: str = ""


@dataclass(slots=True)
class ManagedCodexParseState:
    """Mutable stdout parser state for one managed Codex task run."""

    log_raw_cli_diagnostics: bool = False
    session_id_extracted: bool = False


def build_managed_codex_invocation(
    *,
    config: ManagedCodexConfig,
    request: ManagedCodexTaskRequest,
    base_env: Mapping[str, str],
) -> ManagedCodexInvocation:
    """Build a Codex exec --json subprocess invocation."""

    cmd = build_managed_codex_command(
        codex_bin=config.codex_bin,
        api_url=config.api_url,
        model=config.model,
        prompt=request.prompt,
        session_id=request.session_id,
        fork_session=request.fork_session,
        allowed_dirs=config.allowed_dirs,
    )
    resume_session_id = (
        request.session_id
        if request.session_id
        and not request.session_id.startswith("pending_")
        and not request.fork_session
        else None
    )
    return ManagedCodexInvocation(
        argv=tuple(cmd),
        env=build_codex_launcher_env(
            auth_token=config.auth_token,
            base_env=base_env,
        ),
        cwd=config.workspace_path,
        trace_metadata={
            "client_cli_id": "codex",
            "resume_session_id": resume_session_id,
            "fork_session": request.fork_session,
            "prompt": request.prompt,
            "cwd": config.workspace_path,
            "codex_binary": config.codex_bin,
            "cli_argv": cmd,
        },
    )


def build_managed_codex_command(
    *,
    codex_bin: str,
    api_url: str,
    model: str | None,
    prompt: str,
    session_id: str | None,
    fork_session: bool,
    allowed_dirs: list[str],
) -> list[str]:
    """Return a non-interactive Codex command for a managed task."""

    provider_args = codex_config_args(api_url=api_url, model=model)
    can_resume = (
        session_id is not None
        and not session_id.startswith("pending_")
        and not fork_session
    )
    if can_resume:
        return [
            codex_bin,
            *provider_args,
            "exec",
            "resume",
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "--all",
            session_id,
            prompt,
        ]

    command = [
        codex_bin,
        *provider_args,
        "exec",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
    ]
    for directory in allowed_dirs:
        command.extend(["--add-dir", directory])
    command.append(prompt)
    return command


def parse_managed_codex_stdout_line(
    line: str, state: ManagedCodexParseState
) -> Iterable[Any]:
    """Parse one Codex JSONL stdout line."""

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        if state.log_raw_cli_diagnostics:
            logger.debug("Non-JSON output: {}", line)
        else:
            logger.debug("Non-JSON CLI line: char_len={}", len(line))
        yield {"type": "raw", "content": line}
        return

    if not state.session_id_extracted:
        extracted_id = extract_managed_codex_session_id(event)
        if extracted_id:
            state.session_id_extracted = True
            logger.info("Extracted Codex thread ID: {}", extracted_id)
            yield {"type": "session_info", "session_id": extracted_id}

    yield event


def extract_managed_codex_session_id(event: Any) -> str | None:
    """Extract the resumable thread ID from a Codex JSONL event."""

    if not isinstance(event, dict):
        return None

    for key in ("thread_id", "threadId", "session_id", "sessionId"):
        if value := _string_value(event.get(key)):
            return value

    thread = event.get("thread")
    if isinstance(thread, dict):
        return _string_value(thread.get("id"))
    return None


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
