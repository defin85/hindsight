# Change: Add Ollama embeddings provider

## Why

Hindsight already supports `ollama` as a main LLM provider, but embeddings and
reranking are separate subsystems with their own provider boundaries.

Today, embeddings do not support `ollama` even though Ollama exposes an
official native embeddings API (`/api/embed`) and recommends dedicated
embedding models such as `embeddinggemma`, `qwen3-embedding`, and
`all-minilm`.

That leaves a practical gap for local-first deployments:

- main LLM can run through Ollama
- embeddings cannot
- reranking still needs a different path

This change closes the embeddings gap without pretending that Ollama is also a
first-class reranker API for Hindsight.

## What Changes

- Add a dedicated embeddings provider identified as `ollama`
- Implement it against Ollama's native embeddings API rather than routing
  embeddings through the generic OpenAI-compatible path
- Add configuration and docs for Ollama embeddings, including a local default
  model and base URL normalization rules
- Keep the existing main LLM `ollama` provider unchanged in this change
- Explicitly keep reranker support out of scope for now

## Impact

- Affected specs: `ollama-embeddings-provider`
- Affected code:
  - `hindsight-api-slim/hindsight_api/engine/embeddings.py`
  - `hindsight-api-slim/hindsight_api/config.py`
  - embeddings tests and developer docs
