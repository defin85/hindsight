# Change: Add generic Responses API provider

## Why

Hindsight currently supports `openai-codex` by combining two different concerns
inside one provider:

- authentication through `~/.codex/auth.json`
- a custom Responses-style HTTP/SSE transport that can also be routed through a
  non-ChatGPT endpoint

That coupling makes it difficult to support custom Responses-compatible
endpoints without implying Codex-specific authentication or `codex-lb`
transport assumptions.

## What Changes

- Add a new generic LLM provider named `responses-api` for Responses API
  wire-format endpoints using explicit `api_key` + `base_url` + model
  configuration and no dependency on `~/.codex/auth.json`
- Refactor the current Codex provider so Codex-specific authentication stays
  separate from the shared Responses transport behavior
- Keep the first version minimal: standard provider inputs only
  (`model`, `api_key`, `base_url`, `reasoning_effort`) with no new
  proxy-specific header/body injection knobs
- Document the new provider and configuration surface clearly, including the
  fact that this is Responses-API compatibility, not generic chat-completions
  compatibility
- Add regression tests for provider selection, endpoint resolution, and Codex
  backward compatibility
- Keep local-only `codex-lb`, Docker, backup, and cron workflow concerns out of
  the change scope

## Impact

- Affected specs: `responses-api-provider`
- Affected code:
  - `hindsight-api-slim/hindsight_api/engine/providers/`
  - `hindsight-api-slim/hindsight_api/engine/llm_wrapper.py`
  - `hindsight-api-slim/hindsight_api/config.py`
  - provider tests and docs
