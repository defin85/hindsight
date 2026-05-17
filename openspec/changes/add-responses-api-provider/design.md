## Context

Hindsight already supports multiple LLM transport families:

- native OpenAI/chat-completions-compatible endpoints through
  `OpenAICompatibleLLM`
- Codex/ChatGPT backend access through `CodexLLM`

`CodexLLM` currently owns both Codex authentication and the Responses-style
transport details. That is convenient for local Codex usage, but it makes the
transport impossible to reuse cleanly for non-Codex custom endpoints.

## Goals / Non-Goals

- Goals:
  - add a generic Responses-compatible provider with explicit credentials
  - keep direct Codex support working
  - separate auth concerns from wire-protocol concerns
  - make docs and config semantics explicit
- Non-Goals:
  - replace or remove `openai-codex`
  - add multi-bank orchestration or change memory semantics
  - generalize all "OpenAI-compatible" providers beyond the Responses API scope
  - add local compose or cron-specific operational tooling to upstream-facing
    provider design

## Decisions

### Decision: Introduce a separate generic provider for Responses wire format

Add a provider dedicated to Responses-style endpoints, with explicit `api_key`,
`base_url`, and model configuration.

This provider should not require `~/.codex/auth.json`, should not inject
ChatGPT-specific headers by default, and should clearly describe itself as
Responses-compatible rather than "OpenAI-compatible" in the broad sense.

### Decision: Keep Codex as a thin auth/header specialization

`openai-codex` should remain the Codex/ChatGPT-specific provider, but it should
reuse shared Responses transport logic instead of owning the entire transport
stack itself.

That preserves backward compatibility while removing the current coupling.

### Decision: Use the provider identifier `responses-api`

The generic provider identifier is `responses-api`.

`openai-compatible` already means chat-completions compatibility in many code
bases and tools. Reusing that phrasing for Responses transport would be
misleading.

### Decision: Keep the first version minimal

The first cut should support only the standard provider surface already used by
Hindsight's LLM wrappers: `model`, `api_key`, `base_url`, and
`reasoning_effort`.

It should not introduce provider-specific arbitrary header injection, custom
body fragments, or local-proxy-only knobs in the initial change. That keeps the
protocol boundary small and avoids smuggling `codex-lb`-specific concerns into
an upstream-facing design.

### Decision: Resolve endpoint paths without Codex-specific assumptions

The generic provider should resolve Responses endpoints without appending
Codex-specific `/codex` suffixes.

Normalization rules:

- strip any trailing `/`
- if the configured URL already ends with `/responses`, use it as-is
- otherwise append a final `/responses`
- preserve any operator-supplied intermediate path segments
- never inject an extra `/codex` segment on behalf of the generic provider

Codex-specific `/codex/responses` rules should remain in the Codex-specific
layer, not in the generic provider.

### Decision: Exclude local operational tooling from scope

This change is limited to provider/config/runtime behavior, docs, and tests.

It does not include Docker profiles, `codex-lb` operational packaging, backup
scripts, restore flow, cron automation, or host-specific onboarding.

## Alternatives considered

### Extend `openai` provider with a mode switch

Rejected because it would mix chat-completions and Responses semantics inside
one provider family and make provider behavior harder to predict.

### Add `codex-lb` as a first-class provider

Rejected because it encodes a local transport/proxy product choice instead of a
generic protocol boundary.

### Keep all logic in `CodexLLM`

Rejected because it continues to bind custom Responses routing to Codex auth
and ChatGPT-specific metadata.

## Risks / Trade-offs

- Supporting another wire protocol increases test surface and maintenance cost
- Some "OpenAI-compatible" endpoints support chat-completions only, so docs
  must be careful not to overpromise compatibility
- Provider naming is user-facing; a poor name will create long-term confusion
- Refactoring `CodexLLM` risks subtle regressions in auth/header behavior

## Migration Plan

1. Introduce the generic Responses transport/provider path and tests
2. Refactor `openai-codex` to reuse shared transport logic
3. Add config/docs/examples for the new provider
4. Keep `openai-codex` behavior backward compatible
