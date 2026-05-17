## ADDED Requirements

### Requirement: Successful reflect returns trustworthy token usage

The system SHALL return a trustworthy token usage summary for successful
`reflect` responses that performed LLM work.

#### Scenario: Successful reflect with LLM calls does not return silent zero usage

- **WHEN** a `reflect` request completes successfully after one or more LLM
  calls with non-empty request/response payloads
- **THEN** the response includes a `usage` object
- **AND** `usage.total_tokens` is greater than `0`
- **AND** `usage.total_tokens` equals `usage.input_tokens + usage.output_tokens`

#### Scenario: Aggregated reflect usage remains additive

- **WHEN** reflect performs multiple LLM calls during retrieval, tool use,
  synthesis, or structured-output generation
- **THEN** the final `usage` summary equals the aggregate of those calls
- **AND** it does not silently collapse to `0/0/0` after successful completion

### Requirement: Missing provider-native usage falls back to non-zero accounting

The system SHALL avoid returning misleading zero usage for successful reflect
calls when exact provider-native token counts are unavailable.

#### Scenario: Successful reflect uses fallback accounting

- **WHEN** the LLM provider used by reflect does not return native token usage
- **AND** reflect completed successfully with non-empty LLM request/response
  payloads
- **THEN** Hindsight computes a deterministic fallback usage summary
- **AND** that fallback summary is not `0/0/0`

#### Scenario: Fallback accounting preserves arithmetic consistency

- **WHEN** Hindsight computes fallback usage for reflect
- **THEN** `total_tokens` equals `input_tokens + output_tokens`
