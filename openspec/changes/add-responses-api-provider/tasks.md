## 1. Proposal Readiness

- [x] 1.1 Confirm the final provider identifier and endpoint-resolution rules for the generic Responses provider
- [x] 1.2 Confirm the change scope excludes local-only `codex-lb`, Docker, backup, and cron tooling

## 2. Implementation

- [x] 2.1 Add generic Responses provider/config wiring in `config.py` and `llm_wrapper.py`
- [x] 2.2 Extract or introduce shared Responses transport logic that is not tied to Codex auth
- [x] 2.3 Refactor `openai-codex` to reuse the shared transport while preserving existing auth/header behavior
- [x] 2.4 Add tests for provider selection, endpoint normalization, auth boundaries, and backward compatibility
- [x] 2.5 Update docs/examples to explain the new provider and its scope precisely

## 3. Validation

- [x] 3.1 Run targeted provider tests
- [x] 3.2 Run the repo lint hook
- [x] 3.3 Validate the OpenSpec change with `openspec validate add-responses-api-provider --strict --no-interactive`
