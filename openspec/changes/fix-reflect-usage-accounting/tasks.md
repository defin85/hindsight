## 1. Proposal Readiness

- [ ] 1.1 Confirm the change scope stays focused on reflect token accounting and does not expand into pricing or billing features
- [ ] 1.2 Confirm whether the fix needs only provider fallback changes or also reflect-level aggregation changes

## 2. Implementation

- [ ] 2.1 Reproduce the successful-reflect `usage=0/0/0` path with a focused regression test
- [ ] 2.2 Fix token accounting so successful reflect responses return non-zero usage when LLM work occurred
- [ ] 2.3 Ensure fallback accounting preserves `total_tokens = input_tokens + output_tokens`
- [ ] 2.4 Update docs/comments to explain exact-vs-estimated usage semantics without changing the current API shape

## 3. Validation

- [ ] 3.1 Run targeted reflect/provider token-usage tests
- [ ] 3.2 Run the repo lint hook
- [ ] 3.3 Validate the OpenSpec change with `openspec validate fix-reflect-usage-accounting --strict --no-interactive`
