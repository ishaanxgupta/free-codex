# Architecture

Free Codex is a local inference gateway and launcher for Codex CLI.

## Runtime flow

1. free-codex starts the installed Codex binary with an ephemeral free_codex model provider.
2. Codex sends streaming OpenAI Responses requests to the local FastAPI gateway.
3. the model router resolves the provider-prefixed model selected in configuration or the Codex model picker.
4. a provider adapter converts the request to the upstream provider transport.
5. the Responses adapter converts upstream text, reasoning, tool calls, errors, and usage back to Codex JSON events.

The public client protocol is OpenAI Responses. Anthropic Messages and Chat Completions converters remain internal because some upstream providers expose those protocols.

## Package boundaries

- src/free_codex/api owns FastAPI routes, authentication, Admin UI endpoints, provider execution, model listing, and lifecycle.
- src/free_codex/cli owns the installed commands, Codex launcher, model catalog generation, process registry, and managed Codex sessions.
- src/free_codex/config owns settings, managed paths, provider metadata, and logging.
- src/free_codex/core/openai_responses owns Responses request and stream conversion.
- src/free_codex/core/anthropic owns internal message-protocol conversion used by compatible upstreams.
- src/free_codex/providers owns provider construction, transports, rate limiting, and concrete adapters.
- src/free_codex/messaging owns Discord and Telegram workflows, transcript rendering, persistence, and voice handoff.

## Installed commands

- free-codex launches Codex with runtime provider overrides and a generated model catalog.
- free-codex-server starts the gateway and local Admin UI.
- free-codex-init creates ~/.free-codex/.env.

The launcher strips inherited OpenAI credentials, places the gateway token in FREE_CODEX_API_KEY, and passes the provider through Codex -c overrides. User configuration is not modified.

## Managed messaging

Messaging sessions use codex exec --json. The first thread.started event provides the resumable thread ID. Replies use codex exec resume. Fork requests intentionally start a new Codex thread because the exec surface does not expose thread forking.

Codex JSONL items are normalized into transcript events:

- agent_message becomes visible text;
- reasoning becomes a collapsible reasoning segment;
- command_execution becomes a shell tool call and result;
- file_change becomes an apply_patch tool event;
- mcp_tool_call becomes a named external tool event.

## Configuration and state

Managed state lives under ~/.free-codex:

- .env stores provider credentials and runtime settings;
- codex-model-catalog.json powers the native model picker;
- agent_workspace stores messaging sessions;
- logs/server.log stores gateway logs.

FREE_CODEX_ENV_FILE can append an explicit dotenv source. Process environment values have highest precedence except when the managed dotenv explicitly owns the gateway auth token.

## Security boundaries

- Admin routes are loopback-only.
- Proxy routes accept X-API-Key or Bearer authentication when FREE_CODEX_AUTH_TOKEN is set.
- Secrets are redacted from structured traces.
- Raw API bodies and CLI output are opt-in diagnostics.
- Web fetch blocks private network targets by default.
- Messaging should use a dedicated ALLOWED_DIR because it runs Codex without interactive approval prompts.

## Verification

Deterministic tests cover routes, providers, streaming contracts, configuration, installers, launchers, managed sessions, messaging, and import boundaries. Live provider and client checks live under smoke and are opt-in.
