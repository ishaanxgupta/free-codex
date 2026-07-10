# Repository guidance

Free Codex targets Python 3.14 and uses Astral uv.

## Commands

- Use uv run for Python commands.
- Format with uv run ruff format.
- Lint with uv run ruff check.
- Type-check with uv run ty check.
- Test with uv run pytest.
- Run scripts/ci.sh or scripts/ci.ps1 before publishing.

## Engineering rules

- Add tests for behavior changes and edge cases.
- Keep the OpenAI Responses client contract stable for Codex.
- Keep provider-specific quirks inside provider modules.
- Put shared Responses behavior under src/free_codex/core/openai_responses.
- Anthropic modules are internal provider-compatibility code, not a public Claude client surface.
- Never add type-ignore suppressions; fix the type boundary.
- Do not log raw prompts, provider payloads, or secrets by default.
- Support Windows, macOS, and Linux unless a feature is explicitly platform-specific.
- Keep README.md, ARCHITECTURE.md, installers, and .env.example aligned with public behavior.
- Bump pyproject.toml and refresh uv.lock for release-facing production changes.

## Summary format

Report files changed, logic altered, verification performed, and residual risks.
