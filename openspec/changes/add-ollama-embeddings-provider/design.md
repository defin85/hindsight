## Context

Hindsight has three model-dependent layers with separate abstractions:

- main LLM
- embeddings
- reranker

`ollama` is already supported for the main LLM path, but embeddings and
reranking use different factories and provider contracts. The current
embeddings providers include `local`, `tei`, `openai`, `cohere`, `google`,
`litellm`, and `litellm-sdk`, but not `ollama`.

Ollama has an official native embeddings endpoint (`/api/embed`) and recommends
dedicated embedding models. By contrast, Hindsight's reranker layer expects a
cross-encoder or rerank-style provider contract, and Ollama does not expose an
official first-class `/rerank` API boundary to match that contract.

## Goals / Non-Goals

- Goals:
  - add native Ollama support to the embeddings subsystem
  - keep the design honest about Ollama capability boundaries
  - avoid unnecessary refactoring of the already-working main LLM path
  - document a clean local-first configuration for `LLM + embeddings`
- Non-Goals:
  - refactor the existing main LLM `ollama` implementation
  - add an Ollama reranker provider in this change
  - redesign all embeddings providers or all local-model workflows
  - add migration automation for dimension changes

## Decisions

### Decision: Add Ollama only to embeddings in this change

The practical gap is in embeddings, not the main LLM path.

The repo already supports `ollama` for main LLM calls, so this change should
not spend scope on refactoring that path unless a separate bug or capability
gap justifies it later.

### Decision: Use Ollama native `/api/embed`

The embeddings provider should call Ollama's native embeddings API rather than
shoehorning embeddings through an OpenAI-compatible adapter.

That keeps the provider aligned with Ollama's actual capability boundary and
lets Hindsight rely on Ollama's documented behavior for batch input and
normalized vectors.

### Decision: Keep reranker out of scope

This change should not add `HINDSIGHT_API_RERANKER_PROVIDER=ollama`.

Even though reranker models may exist in the Ollama model library, Hindsight's
reranker layer expects a stable rerank or cross-encoder provider contract, and
Ollama does not currently expose an official rerank API surface that matches
that contract cleanly.

The supported local reranker story remains `tei` or `local`.

### Decision: Keep the first configuration surface minimal

The first cut should add only the settings needed to make Ollama embeddings
usable:

- `HINDSIGHT_API_EMBEDDINGS_PROVIDER=ollama`
- `HINDSIGHT_API_EMBEDDINGS_OLLAMA_MODEL`
- `HINDSIGHT_API_EMBEDDINGS_OLLAMA_BASE_URL`
- optional `HINDSIGHT_API_EMBEDDINGS_OLLAMA_API_KEY` for non-local/Ollama Cloud
  style deployments

The default model should be an official Ollama embedding model rather than a
chat model. `embeddinggemma` is the recommended default.

### Decision: Normalize Ollama embeddings base URLs to the native API root

Operators may reasonably configure any of these forms:

- `http://localhost:11434`
- `http://localhost:11434/api`
- `http://localhost:11434/v1`

The provider should normalize them into a final native embed endpoint rooted at
`/api/embed`.

This avoids forcing users to reason about whether they are configuring the host
root, the native API root, or the OpenAI-compatible `/v1` root.

## Alternatives considered

### Reuse the OpenAI-compatible embeddings path

Rejected because Ollama already has a native embeddings API and the repo's
existing embeddings abstraction is not limited to OpenAI-compatible transports.

### Add `ollama` to embeddings and reranker together

Rejected because the capability boundary is asymmetric: embeddings are first
class in Ollama, reranking is not.

### Refactor main LLM Ollama first

Rejected for this change because it expands scope without solving the current
product gap.

## Risks / Trade-offs

- Adding Ollama embeddings creates another model family with its own embedding
  dimensions, so operators can still break compatibility by changing models on
  a non-empty database
- Cloud-style Ollama auth behavior may vary more than local daemon usage
- If operators expect `ollama` to work everywhere after this change, docs must
  be explicit that reranker support is still separate

## Migration Plan

1. Add `ollama` as an embeddings provider with native `/api/embed` calls
2. Add validation and tests for URL normalization, batching, and dimension
   handling
3. Update docs to show `ollama` is supported for main LLM and embeddings, but
   not as a first-class reranker provider
