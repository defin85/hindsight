# AGENTS.md

See [CLAUDE.md](./CLAUDE.md) for project documentation and coding conventions.

## Project Memory Workflow

- For repo-local Hindsight project memory, do not use sync `Hindsight(...).retain()` or `retain_batch(..., retain_async=False)` in manual runbooks. Those paths wait for fact extraction inline and can hit the client timeout.
- Prefer async retain for manual progress notes: `POST /v1/default/banks/{bank_id}/memories` with `"async": true`, or Python `retain_batch(..., retain_async=True)`.
- After submit, poll `GET /v1/default/banks/{bank_id}/operations/{operation_id}` until the operation reaches `completed` or `failed`.
- Recall and reflect can stay synchronous for normal repo work.
- When verifying that a malformed bank was deleted, check the bank list. Do not call `/stats` on the deleted `bank_id`, because that endpoint auto-creates an empty bank row.
