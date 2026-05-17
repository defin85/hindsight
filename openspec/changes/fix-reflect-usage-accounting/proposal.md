# Change: Fix reflect token usage accounting

## Why

There is now a practical report from another agent that successful `reflect`
calls on this Hindsight server returned:

- `input_tokens = 0`
- `output_tokens = 0`
- `total_tokens = 0`

That contradicts the current reflect contract and tests, which already expect
successful reflection to return non-zero token usage when LLM calls ran.

Silent `0/0/0` accounting is especially problematic because it is
indistinguishable from "usage unavailable" while still looking like a valid
measurement. That makes cost tracking, debugging, and operational trust in the
server's accounting unreliable.

## What Changes

- Investigate and fix the path that allows successful `reflect` responses to
  return `usage=0/0/0`
- Ensure successful reflect responses return trustworthy usage summaries:
  provider-native counts when available, otherwise deterministic fallback
  estimates when request/response payloads are non-empty
- Keep the first fix backward compatible with the current API shape; do not add
  a new billing or pricing surface in this change
- Add regression coverage for the affected reflect path and any provider-level
  fallback logic involved
- Update docs/comments so operators understand that some providers return exact
  counts while others return estimates, but successful reflect must not silently
  collapse to `0/0/0`

## Impact

- Affected specs: `reflect-usage-accounting`
- Affected code:
  - `hindsight-api-slim/hindsight_api/engine/reflect/`
  - `hindsight-api-slim/hindsight_api/engine/providers/`
  - `hindsight-api-slim/hindsight_api/api/http.py`
  - reflect/provider tests and related docs
