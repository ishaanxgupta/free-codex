import os

from free_codex.cli.managed.codex import (
    ManagedCodexConfig,
    ManagedCodexParseState,
    ManagedCodexTaskRequest,
    build_managed_codex_invocation,
    extract_managed_codex_session_id,
    parse_managed_codex_stdout_line,
)
from free_codex.cli.managed.diagnostics import classify_managed_codex_stderr
from free_codex.messaging.event_parser import parse_cli_event


def _config(**overrides: object) -> ManagedCodexConfig:
    return ManagedCodexConfig(
        workspace_path=str(overrides.get("workspace_path", os.path.normpath("/tmp/workspace"))),
        api_url=str(overrides.get("api_url", "http://localhost:8082/v1")),
        model=str(overrides.get("model", "ollama/qwen3-coder")),
        allowed_dirs=list(overrides.get("allowed_dirs", [])),
        codex_bin=str(overrides.get("codex_bin", "codex")),
        auth_token=str(overrides.get("auth_token", "proxy-token")),
    )


def test_managed_codex_builds_new_task_command_and_env() -> None:
    invocation = build_managed_codex_invocation(
        config=_config(allowed_dirs=[os.path.normpath("/tmp/extra")]),
        request=ManagedCodexTaskRequest(prompt="hello"),
        base_env={"PATH": "keep", "OPENAI_API_KEY": "official"},
    )

    assert invocation.argv[0] == "codex"
    assert "exec" in invocation.argv
    assert "--json" in invocation.argv
    assert "--dangerously-bypass-approvals-and-sandbox" in invocation.argv
    assert "--add-dir" in invocation.argv
    assert os.path.normpath("/tmp/extra") in invocation.argv
    assert invocation.argv[-1] == "hello"
    assert 'model_provider="free_codex"' in invocation.argv
    assert invocation.env["PATH"] == "keep"
    assert invocation.env["FREE_CODEX_API_KEY"] == "proxy-token"
    assert "OPENAI_API_KEY" not in invocation.env
    assert invocation.trace_metadata["client_cli_id"] == "codex"
    assert invocation.trace_metadata["codex_binary"] == "codex"


def test_managed_codex_builds_resume_and_fork_commands() -> None:
    resume = build_managed_codex_invocation(
        config=_config(),
        request=ManagedCodexTaskRequest(prompt="again", session_id="thread-1"),
        base_env={},
    )
    fork = build_managed_codex_invocation(
        config=_config(),
        request=ManagedCodexTaskRequest(
            prompt="branch", session_id="thread-1", fork_session=True
        ),
        base_env={},
    )

    assert resume.argv[resume.argv.index("exec") :][-1] == "again"
    assert "resume" in resume.argv
    assert "thread-1" in resume.argv
    assert "resume" not in fork.argv
    assert fork.argv[-1] == "branch"


def test_managed_codex_env_uses_sentinel_when_proxy_auth_blank() -> None:
    invocation = build_managed_codex_invocation(
        config=_config(auth_token=""),
        request=ManagedCodexTaskRequest(prompt="hello"),
        base_env={"FREE_CODEX_API_KEY": "stale"},
    )

    assert invocation.env["FREE_CODEX_API_KEY"] == "free-codex-no-auth"


def test_managed_codex_stderr_classifier_filters_known_benign_notice() -> None:
    diagnostics = classify_managed_codex_stderr(
        "WARNING: failed to clean up stale arg0 temp dirs"
    )

    assert diagnostics.has_benign
    assert diagnostics.fatal_text is None


def test_managed_codex_stderr_classifier_preserves_unknown_lines() -> None:
    diagnostics = classify_managed_codex_stderr(
        "WARNING: failed to clean up stale arg0 temp dirs\nFatal error"
    )

    assert diagnostics.has_benign
    assert diagnostics.fatal_text == "Fatal error"


def test_managed_codex_extracts_thread_ids() -> None:
    assert extract_managed_codex_session_id({"thread_id": "direct"}) == "direct"
    assert extract_managed_codex_session_id({"threadId": "camel"}) == "camel"
    assert extract_managed_codex_session_id({"thread": {"id": "nested"}}) == "nested"
    assert extract_managed_codex_session_id({"type": "message"}) is None
    assert extract_managed_codex_session_id("not a dict") is None


def test_managed_codex_parser_emits_session_info_once() -> None:
    state = ManagedCodexParseState()

    first = list(
        parse_managed_codex_stdout_line(
            '{"type":"thread.started","thread_id":"thread-1"}', state
        )
    )
    second = list(
        parse_managed_codex_stdout_line(
            '{"type":"thread.started","thread_id":"thread-2"}', state
        )
    )

    assert first == [
        {"type": "session_info", "session_id": "thread-1"},
        {"type": "thread.started", "thread_id": "thread-1"},
    ]
    assert second == [{"type": "thread.started", "thread_id": "thread-2"}]


def test_managed_codex_parser_returns_raw_for_non_json() -> None:
    events = list(
        parse_managed_codex_stdout_line(
            "not json", ManagedCodexParseState(log_raw_cli_diagnostics=False)
        )
    )

    assert events == [{"type": "raw", "content": "not json"}]


def test_codex_agent_message_event_becomes_text() -> None:
    event = {
        "type": "item.completed",
        "item": {"id": "item-1", "type": "agent_message", "text": "Done"},
    }

    assert parse_cli_event(event) == [{"type": "text_chunk", "text": "Done"}]


def test_codex_command_event_becomes_tool_pair() -> None:
    event = {
        "type": "item.completed",
        "item": {
            "id": "item-1",
            "type": "command_execution",
            "command": "git status",
            "aggregated_output": "clean",
            "status": "completed",
        },
    }

    assert parse_cli_event(event) == [
        {
            "type": "tool_use",
            "id": "item-1",
            "name": "shell",
            "input": {"command": "git status"},
        },
        {
            "type": "tool_result",
            "tool_use_id": "item-1",
            "content": "clean",
            "is_error": False,
        },
    ]
