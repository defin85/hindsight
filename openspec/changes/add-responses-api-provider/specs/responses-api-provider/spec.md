## ADDED Requirements

### Requirement: Generic Responses API provider

The system SHALL provide a generic LLM provider identified as `responses-api`
for Responses API wire-format endpoints that can be configured with explicit
credentials and a custom base URL, without requiring Codex CLI OAuth state.

#### Scenario: Custom Responses endpoint without Codex auth

- **WHEN** an operator configures the generic Responses provider with a model,
  base URL, and API key
- **THEN** Hindsight uses that provider for LLM calls without requiring
  `~/.codex/auth.json`

#### Scenario: Initial provider surface stays minimal

- **WHEN** an operator configures `responses-api`
- **THEN** the documented provider contract is limited to the standard LLM
  inputs `model`, `api_key`, `base_url`, and `reasoning_effort`

#### Scenario: Provider scope is explicit

- **WHEN** the generic Responses provider is documented or configured
- **THEN** the system describes it as Responses-API compatibility rather than
  generic chat-completions compatibility
- **AND** the provider contract does not depend on local-only `codex-lb`,
  Docker, backup, or cron workflow setup

### Requirement: Codex authentication remains provider-specific

The system SHALL keep Codex/ChatGPT-specific authentication and header behavior
separate from the generic Responses provider.

#### Scenario: Direct Codex provider still uses Codex auth

- **WHEN** an operator configures `openai-codex`
- **THEN** Hindsight still loads Codex CLI OAuth credentials and applies any
  Codex-specific request metadata required by that provider

#### Scenario: Generic provider does not inherit Codex metadata

- **WHEN** an operator configures the generic Responses provider
- **THEN** Hindsight does not implicitly require or inject Codex-specific auth
  files or ChatGPT-specific headers

### Requirement: Responses endpoint resolution is protocol-oriented

The system SHALL resolve generic Responses provider endpoints by normalizing the
configured URL into a final `/responses` endpoint without Codex-specific path
assumptions.

#### Scenario: Full endpoint URL is accepted as-is

- **WHEN** the configured base URL already points to a final `/responses`
  endpoint
- **THEN** Hindsight uses that endpoint directly

#### Scenario: Generic root URL resolves to Responses endpoint

- **WHEN** the configured base URL points to a generic Responses-compatible
  service root rather than a final `/responses` path
- **THEN** Hindsight strips any trailing slash, appends a final `/responses`
- **AND** it does not append Codex-specific `/codex` segments on its own
