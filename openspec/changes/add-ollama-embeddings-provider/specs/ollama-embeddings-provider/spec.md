## ADDED Requirements

### Requirement: Ollama is supported as an embeddings provider

The system SHALL support `ollama` as a first-class embeddings provider using
Ollama's native embeddings API.

#### Scenario: Configure Ollama embeddings locally

- **WHEN** an operator sets `HINDSIGHT_API_EMBEDDINGS_PROVIDER=ollama`
- **AND** provides an Ollama embedding model or uses the provider default
- **THEN** Hindsight initializes embeddings through Ollama's native embed API

#### Scenario: Batch embedding requests are supported

- **WHEN** Hindsight sends multiple texts for embedding with the Ollama
  embeddings provider
- **THEN** the provider sends a batch request to Ollama
- **AND** returns one embedding vector per input text

### Requirement: Ollama embeddings URLs normalize to the native embed endpoint

The system SHALL normalize Ollama embeddings base URLs to the native
`/api/embed` endpoint.

#### Scenario: Host root is normalized

- **WHEN** the configured Ollama embeddings base URL is `http://host:11434`
- **THEN** Hindsight calls `http://host:11434/api/embed`

#### Scenario: Native API root is normalized

- **WHEN** the configured Ollama embeddings base URL is `http://host:11434/api`
- **THEN** Hindsight calls `http://host:11434/api/embed`

#### Scenario: OpenAI-compatible root is normalized

- **WHEN** the configured Ollama embeddings base URL is `http://host:11434/v1`
- **THEN** Hindsight still resolves the final endpoint to `http://host:11434/api/embed`

### Requirement: Ollama support does not imply reranker support

The system SHALL keep Ollama embeddings support separate from reranker support.

#### Scenario: Ollama embeddings does not add Ollama reranker

- **WHEN** an operator enables Ollama embeddings
- **THEN** Hindsight does not implicitly expose `ollama` as a reranker provider
- **AND** documentation continues to direct local reranker usage to supported
  reranker providers such as `tei` or `local`
