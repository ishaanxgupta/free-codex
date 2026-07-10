<div align="center">

# Free Codex

Run Codex CLI with free, local, or provider-hosted models through a local OpenAI Responses gateway.

[Quick start](#quick-start) | [Providers](#providers) | [How it works](#how-it-works) | [Development](#development)

</div>

Free Codex keeps the Codex terminal experience - tool use, streaming, resumable threads, and the native model picker - while routing inference through a provider you control.

## Features

- First-class free-codex, free-codex-server, and free-codex-init commands.
- OpenAI Responses-compatible gateway for Codex CLI and the Codex editor extension.
- 24 cloud and local provider adapters.
- Local Admin UI for credentials, model selection, validation, and runtime settings.
- Generated model catalog for the native /model picker.
- Streaming text, reasoning, tool calls, usage accounting, retry handling, and protocol error mapping.
- Optional Discord and Telegram sessions backed by codex exec --json.
- Optional local or NVIDIA NIM voice transcription.
- Windows, macOS, and Linux lifecycle scripts.
- Deterministic provider, protocol, API, messaging, and CLI tests.

## Quick start

### 1. Clone and install

    git clone https://github.com/ishaanxgupta/free-codex.git
    cd free-codex

macOS or Linux:

    sh scripts/install.sh

Windows PowerShell:

    .\scripts\install.ps1

The installer provisions Codex CLI when missing, Astral uv, Python 3.14, and the Free Codex tool.

### 2. Initialize configuration

    free-codex-init

This creates ~/.free-codex/.env.

### 3. Start the gateway

    free-codex-server

The Admin UI opens at http://127.0.0.1:8082/admin by default.

### 4. Add a provider key and select a model

Open the Admin UI, select a provider, add its API key or local server URL, and
choose **Test connection**. After the provider returns its available models,
select a default model and choose **Apply changes**. Provider keys are stored
locally in `~/.free-codex/.env` and are never shown again by the Admin UI.

For a no-cost cloud starting point, enter these values in the Admin UI:

    OPENROUTER_API_KEY="..."
    MODEL="open_router/openrouter/free"

For Ollama:

    OLLAMA_BASE_URL="http://localhost:11434"
    MODEL="ollama/qwen3-coder"

Apply the settings in the Admin UI, restart the gateway if prompted, then launch
Codex in a second terminal:

    free-codex

All normal Codex arguments are forwarded:

    free-codex exec "explain this repository"
    free-codex --sandbox workspace-write --ask-for-approval never

Inside Codex, use /model to select a model exposed by the gateway.

## Providers

| Provider | Credential or setting | Example model |
| --- | --- | --- |
| [OpenRouter](https://openrouter.ai/) | `OPENROUTER_API_KEY` | `open_router/openrouter/free` |
| [NVIDIA NIM](https://build.nvidia.com/) | `NVIDIA_NIM_API_KEY` | `nvidia_nim/nvidia/nemotron-3-super-120b-a12b` |
| [Gemini](https://aistudio.google.com/) | `GEMINI_API_KEY` | `gemini/models/gemini-3.1-flash-lite` |
| [DeepSeek](https://platform.deepseek.com/) | `DEEPSEEK_API_KEY` | `deepseek/deepseek-chat` |
| [Mistral](https://console.mistral.ai/) | `MISTRAL_API_KEY` | `mistral/devstral-small-latest` |
| [Mistral Codestral](https://console.mistral.ai/) | `CODESTRAL_API_KEY` | `mistral_codestral/codestral-latest` |
| [OpenCode Zen](https://opencode.ai/) | `OPENCODE_API_KEY` | `opencode/gpt-5.3-codex` |
| [OpenCode Go](https://opencode.ai/) | `OPENCODE_API_KEY` | `opencode_go/minimax-m2.7` |
| [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) | `AI_GATEWAY_API_KEY` | `vercel/openai/gpt-5.5` |
| [Hugging Face](https://huggingface.co/) | `HUGGINGFACE_API_KEY` | `huggingface/openai/gpt-oss-120b:fastest` |
| [Cohere](https://cohere.com/) | `COHERE_API_KEY` | `cohere/command-a-plus-05-2026` |
| [GitHub Models](https://github.com/marketplace/models) | `GITHUB_MODELS_TOKEN` | `github_models/openai/gpt-4.1` |
| [Wafer](https://www.wafer.ai/) | `WAFER_API_KEY` | `wafer/DeepSeek-V4-Pro` |
| [Kimi](https://platform.moonshot.cn/) | `KIMI_API_KEY` | `kimi/kimi-k2.5` |
| [MiniMax](https://www.minimax.io/) | `MINIMAX_API_KEY` | `minimax/MiniMax-M3` |
| [Groq](https://console.groq.com/) | `GROQ_API_KEY` | `groq/llama-3.3-70b-versatile` |
| [Cerebras](https://cloud.cerebras.ai/) | `CEREBRAS_API_KEY` | `cerebras/gpt-oss-120b` |
| [SambaNova](https://cloud.sambanova.ai/) | `SAMBANOVA_API_KEY` | `sambanova/Meta-Llama-3.3-70B-Instruct` |
| [Fireworks](https://fireworks.ai/) | `FIREWORKS_API_KEY` | `fireworks/accounts/fireworks/models/llama-v3p3-70b-instruct` |
| [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) | `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` | `cloudflare/@cf/moonshotai/kimi-k2.6` |
| [Z.ai](https://z.ai/) | `ZAI_API_KEY` | `zai/glm-5.2` |
| [Ollama](https://ollama.com/) | `OLLAMA_BASE_URL` | `ollama/qwen3-coder` |
| [LM Studio](https://lmstudio.ai/) | `LM_STUDIO_BASE_URL` | `lmstudio/model-id` |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | `LLAMACPP_BASE_URL` | `llamacpp/model-id` |

The Admin UI contains the complete provider catalog and provider-specific validation.

Free Codex does not provide models or bypass provider terms. "Free" means you can use free-tier or local inference when the selected provider offers it.

## Configuration

Important settings in ~/.free-codex/.env:

    MODEL="open_router/openrouter/free"
    FREE_CODEX_AUTH_TOKEN="free-codex"
    FREE_CODEX_OPEN_BROWSER=true
    PROVIDER_MAX_CONCURRENCY=5
    HTTP_READ_TIMEOUT=300

The launcher injects an ephemeral Codex provider equivalent to:

    model_provider = "free_codex"

    [model_providers.free_codex]
    name = "Free Codex"
    base_url = "http://127.0.0.1:8082/v1"
    env_key = "FREE_CODEX_API_KEY"
    wire_api = "responses"

No permanent changes to the user's Codex configuration are required.

## Codex editor extension

Create or update ~/.codex/config.toml (or %USERPROFILE%\.codex\config.toml on Windows) with the provider block above. Store the configured gateway token in ~/.codex/auth.json:

    {
      "FREE_CODEX_API_KEY": "free-codex"
    }

Restart the editor after changing Codex configuration.

## Optional messaging

Configure Discord or Telegram from Admin UI -> Messaging. Managed conversations run through codex exec --json; replies resume the recorded Codex thread.

Because messaging execution is unattended, restrict ALLOWED_DIR to a dedicated workspace and protect the gateway and bot credentials.

## How it works

    Codex CLI / extension
              |
              v
    Free Codex Responses gateway
              |
              v
         Model router
              |
              v
      Cloud or local provider

Codex sends OpenAI Responses requests to the local gateway. Free Codex converts those requests to the selected provider's native or OpenAI-compatible transport, then converts streaming output back to Responses events Codex understands.

Some providers expose Chat Completions or Anthropic-compatible message APIs rather than Responses. Those protocol converters are internal gateway details; the public client surface remains Codex Responses.

See [ARCHITECTURE.md](ARCHITECTURE.md) for package boundaries and extension points.

## Security

- The Admin API is loopback-only.
- Set FREE_CODEX_AUTH_TOKEN when the gateway is reachable by anything other than your local user.
- API keys are stored in the managed dotenv file and redacted from structured traces.
- Raw prompts and provider payloads are not logged unless diagnostic flags are explicitly enabled.
- Messaging uses unattended Codex execution; use an isolated workspace and narrow bot allowlists.
- Review provider privacy, retention, and acceptable-use policies before sending source code.

## Development

Requirements: uv 0.11 or newer and Python 3.14.

    uv sync
    uv run ruff format
    uv run ruff check
    uv run ty check
    uv run pytest

Run the platform CI helper before contributing:

    ./scripts/ci.sh

or:

    .\scripts\ci.ps1

## Uninstall

macOS or Linux:

    ./scripts/uninstall.sh

Windows PowerShell:

    .\scripts\uninstall.ps1

The uninstaller removes the Free Codex uv tool and ~/.free-codex/. It does not remove Codex CLI, uv, or uv-managed Python runtimes.

## License

MIT. See [LICENSE](LICENSE).
