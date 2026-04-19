# Hindsight Local Docker + PostgreSQL + TEI

This profile keeps Hindsight stateless and moves persistence into a dedicated
PostgreSQL container backed by a named Docker volume. It avoids the embedded
`pg0` path that was previously reset after restart.

The stack is split into four services:

- API: built locally from the current checkout, so Codex LB fixes from this repo
  are used immediately.
- Control Plane: runs as a separate container and talks to the API over the
  internal compose network.
- TEI embeddings: runs `BAAI/bge-base-en-v1.5` on the local GPU.
- TEI reranker: runs `BAAI/bge-reranker-base` on the local GPU.

The default LLM wiring matches a local Codex CLI setup behind `codex-lb`:

- provider: `openai-codex`
- model: `gpt-5.4`
- reasoning effort: `xhigh`
- base URL: `http://host.docker.internal:2455/backend-api/codex`

The default TEI wiring uses officially supported Hugging Face models and the
official Blackwell container image for RTX 50xx:

- TEI image: `ghcr.io/huggingface/text-embeddings-inference:120-1.9`
- embeddings model: `BAAI/bge-base-en-v1.5`
- reranker model: `BAAI/bge-reranker-base`

## Quick start

```bash
cp docker/docker-compose/local-pg/.env.example docker/docker-compose/local-pg/.env
```

Edit `docker/docker-compose/local-pg/.env` and set at least:

- `HINDSIGHT_DB_PASSWORD`
- `CODEX_LB_API_KEY`
- `HINDSIGHT_CODEX_AUTH_DIR`

`HINDSIGHT_CODEX_AUTH_DIR` must point to the host directory that contains your
Codex CLI `auth.json` file. Run `codex auth login` first if that directory does
not exist yet.

Start the stack:

```bash
docker compose -f docker/docker-compose/local-pg/docker-compose.yaml --env-file docker/docker-compose/local-pg/.env up -d --build
```

The first start is slower because:

- the API image is built locally
- both TEI containers download model weights into named Docker volumes

If your current non-Docker Hindsight is still running on `8889` or `9999`,
stop it first or change `HINDSIGHT_HOST_API_PORT` / `HINDSIGHT_HOST_CP_PORT`
in `.env`.

The container reaches the Codex load balancer through
`host.docker.internal:2455`, so the proxy must already be running on the host.

If you want different officially supported TEI models, change:

- `HINDSIGHT_API_EMBEDDINGS_TEI_MODEL_ID`
- `HINDSIGHT_API_RERANKER_TEI_MODEL_ID`

Keep the model choice within Hugging Face models that are compatible with
Text Embeddings Inference.

Check status:

```bash
docker compose -f docker/docker-compose/local-pg/docker-compose.yaml --env-file docker/docker-compose/local-pg/.env ps
```

Access:

- API: `http://localhost:8889`
- Control Plane: `http://localhost:9999/dashboard`

## Notes

- This profile keeps the main LLM on `codex-lb` and uses TEI only for
  embeddings and reranking.
- The API image is built with `INCLUDE_LOCAL_MODELS=false`, so local
  sentence-transformers weights are not baked into the Hindsight container.
- TEI uses named volumes under Docker, so model weights survive container
  recreation.

## Backups

Create a PostgreSQL dump:

```bash
./docker/docker-compose/local-pg/backup.sh
```

By default dumps go to:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/hindsight/backups
```

The script writes outside the PostgreSQL Docker volume, so a recreated
container or volume does not delete the dump files.

Retention defaults to keeping the latest 5 timestamped dumps in that
directory. Override it with `HINDSIGHT_BACKUP_KEEP`.

Restore from a dump:

```bash
./docker/docker-compose/local-pg/restore.sh /home/egor/.local/state/hindsight/backups/hindsight-YYYYMMDDTHHMMSSZ.dump
```

The restore script is destructive by design:

- it stops `hindsight-api` and `hindsight-cp` if they are running
- drops and recreates the configured PostgreSQL database
- restores the dump into the recreated database
- starts the previously running app services again

Use `--yes` to skip the interactive confirmation.

## Cron

The profile includes an installer for a daily cron job:

```bash
sudo ./docker/docker-compose/local-pg/install-cron.sh
```

Default schedule:

```text
0 22 * * *
```

This runs `backup.sh` daily at 22:00 local time, keeps the latest 5 dumps,
and appends logs to:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/hindsight/backup-cron.log
```

Change the schedule before install with `HINDSIGHT_BACKUP_SCHEDULE`, for
example:

```bash
HINDSIGHT_BACKUP_SCHEDULE='42 2 * * *' sudo -E ./docker/docker-compose/local-pg/install-cron.sh
```

## Stop

```bash
docker compose -f docker/docker-compose/local-pg/docker-compose.yaml --env-file docker/docker-compose/local-pg/.env down
```

Do not use `down -v` unless you intentionally want to delete the database
volume.
