## Context

Hindsight already exposes token usage in reflect responses and has tests that
assert successful reflect calls return positive usage totals. The current local
server, however, was reported to return `0/0/0` on successful reflect calls.

The current implementation has two relevant layers:

- provider-level usage reporting, which may be exact or estimated
- reflect-level aggregation, which combines usage across multiple LLM calls

The issue could originate in either layer. This change therefore focuses on the
end-to-end contract at the reflect boundary while allowing the implementation
fix to land in the provider path, the reflect aggregation path, or both.

## Goals / Non-Goals

- Goals:
  - restore trustworthy token accounting for successful reflect responses
  - prevent silent `0/0/0` summaries after real LLM work occurred
  - keep the existing response shape compatible for the first fix
  - document exact-vs-estimated usage semantics more clearly
- Non-Goals:
  - add pricing, billing, or per-model cost computation
  - redesign every endpoint's accounting semantics in one change
  - introduce a broad telemetry refactor unrelated to reflect correctness
  - add local operational runbooks, cron logic, or deployment-specific caveats

## Decisions

### Decision: Keep the current response shape in the first fix

The initial fix should preserve the existing `usage` object shape:

- `input_tokens`
- `output_tokens`
- `total_tokens`

That keeps the change narrow and avoids forcing SDK/schema churn just to fix a
correctness regression in the accounting path.

### Decision: Prefer exact provider counts, but require a reliable fallback

If the provider returns native token usage, Hindsight should use it.

If the provider does not return native usage, Hindsight should compute a
deterministic fallback estimate from the real request/response payloads used by
the call.

For successful reflect calls with non-empty LLM request/response content, that
fallback must not silently produce `0/0/0`.

### Decision: Treat all-zero usage after successful LLM work as invalid

For this change, an all-zero usage summary is not a trustworthy accounting
signal once reflect has successfully completed at least one non-empty LLM call.

The implementation should replace that invalid accounting outcome with a
fallback estimate rather than returning a misleading zero summary.

### Decision: Scope acceptance at the reflect contract boundary

The user-visible contract to restore is the reflect API behavior:

- successful reflect must not silently return `usage=0/0/0` after real LLM work
- `total_tokens` must remain equal to `input_tokens + output_tokens`

The implementation may fix this in a shared provider path if that is the actual
root cause, but acceptance remains focused on reflect behavior.

## Alternatives considered

### Add a new `estimated` or `usage_source` field immediately

Deferred for now.

That could be valuable later, but it expands API/schema surface and is not
required to fix the immediate correctness problem of successful reflect calls
returning misleading zero usage.

### Leave usage at zero when exact counts are unavailable

Rejected because it preserves the current ambiguity and keeps token accounting
operationally untrustworthy.

## Risks / Trade-offs

- Estimated counts are still not billing-grade exact values
- Some provider/tool-call payload shapes may need better fallback estimation
  than a naive text-length heuristic
- Fixing reflect first may still leave similar zero-accounting problems in
  other endpoints if they share the same provider path but lack explicit tests

## Migration Plan

1. Reproduce the zero-usage reflect path with a focused regression test
2. Fix the provider and/or reflect aggregation path so successful reflect
   returns non-zero usage when LLM work occurred
3. Update docs/comments to clarify exact-vs-estimated usage behavior
4. Validate targeted tests, lint, and strict OpenSpec consistency
