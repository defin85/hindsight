## 1. Proposal Readiness

- [ ] 1.1 Confirm the change is limited to embeddings and does not refactor the current main LLM `ollama` path
- [ ] 1.2 Confirm reranker support remains explicitly out of scope

## 2. Implementation

- [ ] 2.1 Add `ollama` to the embeddings provider configuration surface
- [ ] 2.2 Implement native Ollama `/api/embed` support with batch input handling
- [ ] 2.3 Normalize Ollama embeddings base URLs into a final native embed endpoint
- [ ] 2.4 Add tests for provider creation, URL normalization, and embedding response handling
- [ ] 2.5 Update docs/examples to explain the supported `ollama` scope precisely

## 3. Validation

- [ ] 3.1 Run targeted embeddings/provider tests
- [ ] 3.2 Run the repo lint hook
- [ ] 3.3 Validate the OpenSpec change with `openspec validate add-ollama-embeddings-provider --strict --no-interactive`
