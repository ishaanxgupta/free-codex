# Contributing

Thanks for improving Free Codex.

## Setup

    uv sync

## Checks

    uv run ruff format
    uv run ruff check
    uv run ty check
    uv run pytest

Or run the platform helper:

    ./scripts/ci.sh

    .\scripts\ci.ps1

Keep changes focused, add deterministic tests, and preserve the Codex Responses contract. Live provider tests must remain opt-in and must never require contributor credentials for the default suite.

By contributing, you agree that your work is licensed under the repository MIT license.
