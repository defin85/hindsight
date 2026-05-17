# Project Context

## Purpose
Hindsight is an agent memory system for long-term memory in AI agents. It stores
facts, experiences, and mental models in bank-scoped memory stores and exposes
retain, recall, and reflect APIs plus framework integrations and an admin UI.

## Tech Stack
- Python 3.13 with FastAPI and uv (`hindsight-api-slim/`, `hindsight-api/`)
- PostgreSQL with pgvector and Alembic migrations
- TypeScript / Next.js for the control plane UI (`hindsight-control-plane/`)
- Rust for the CLI (`hindsight-cli/`)
- Docusaurus for docs (`hindsight-docs/`)
- Generated SDK clients for Python, TypeScript, and Rust

## Project Conventions

### Code Style
- Follow existing repo conventions and keep changes scoped and pragmatic.
- Use ASCII in source edits unless the file already needs Unicode.
- Read files before editing and prefer root-cause fixes over local workarounds.
- Python changes should pass `ruff check`, `ruff format`, and the repo lint hook.
- TypeScript/Next.js changes should pass the repo lint hook and keep client/API
  parameter wiring in sync.
- Generated artifacts (for example OpenAPI or SDK outputs) should only be
  regenerated when the change requires them.

### Architecture Patterns
- Monorepo with separate packages for API server, slim core engine, control
  plane UI, CLI, generated clients, docs, integrations, and dev tooling.
- Bank isolation is strict: every API request operates on one memory bank.
- Multi-bank orchestration is client-side responsibility.
- The memory engine centralizes retain/recall/reflect orchestration under
  `hindsight-api-slim/hindsight_api/engine/`.
- LLM providers are selected through `llm_wrapper.py` and provider-specific
  implementations under `engine/providers/`.
- Control-plane API routes proxy to the dataplane API and must stay aligned
  with backend request parameters.

### Testing Strategy
- Run the smallest relevant verification set for the change and report it.
- Repo-wide lint gate: `./scripts/hooks/lint.sh`
- Python tests usually run from `hindsight-api-slim` via `uv run pytest ...`
- API or schema changes may require regeneration and verification of OpenAPI or
  generated clients.
- Do not claim completion if required behavior is deferred into TODO/FIXME.

### Git Workflow
- Work is currently happening on `main` in the local clone, but changes should
  still be scoped cleanly and validated before commit.
- Keep commits focused and non-destructive; do not revert unrelated user work.
- For agent memory and planning work, prefer explicit runbooks over hidden
  automation.

## Domain Context
- Hindsight organizes memory as world facts, experiences, and mental models.
- Banks act like isolated "brains" for users, agents, or projects.
- Retain stores and extracts memories, recall retrieves relevant memory units,
  and reflect performs disposition-aware reasoning over retrieved context.
- Disposition traits affect reflect behavior, not recall behavior.
- Some local workflows use Hindsight itself as manual project memory via the
  local API at `http://127.0.0.1:8889`.

## Important Constraints
- PostgreSQL/pgvector is the primary persistence path; migrations are managed by
  Alembic and must stay compatible.
- All endpoints operate on a single bank per request.
- Control-plane parameter changes must also update the proxy routes and client
  types in `hindsight-control-plane/src/lib/api.ts`.
- New integrations under `hindsight-integrations/` require tests, CI wiring, and
  release-script registration before they are complete.
- Avoid storing secrets or raw credentials in project memory artifacts.

## External Dependencies
- LLM providers including OpenAI, Anthropic, Gemini, Groq, Ollama, LM Studio,
  MiniMax, OpenRouter, Vertex AI, Bedrock, and provider-specific wrappers
- PostgreSQL with pgvector
- Hugging Face / sentence-transformers / TEI for embeddings and reranking
- npm workspace tooling for UI/docs packages
- Rust toolchain for the CLI
