# Architecture

## Layer rules
- `app/infrastructure/` — external clients only (HTTP, transport). Connection setup and model selection. No business logic.
- `app/utils/` — reusable pure utilities (file encoding, formatting). No domain knowledge, no LLM calls.
- `app/prompts/` — prompt text constants only. One file per domain (e.g. `branding.py`). No logic.
- `app/services/` — business logic: assembles prompt + utils + client, parses and seeds results.
- `app/db.py` — data layer: SQL only. No business logic.
- `app/graph.py` — orchestration: LangGraph nodes call services, nothing else.
- `app/config.py` — single source of env vars. No logic.
- `cli.py` — entry point: UI loop + graph runner only.

## Where to put new things
| What | Where |
|------|-------|
| New LLM prompt | `app/prompts/<domain>.py` as an UPPER_CASE constant |
| New LLM feature (call + parse) | `app/services/<domain>.py` |
| New external API client | `app/infrastructure/<adapter>.py` |
| New reusable utility | `app/utils/<topic>.py` |
| New SQL query | `app/db.py` |
| New graph node | `app/graph.py` (node calls a service) |
| New env variable | `app/config.py` |

## Naming
- Prompts: `UPPER_CASE_PROMPT` constant in `app/prompts/<domain>.py`
- Services: `app/services/<domain>.py`
- Infrastructure: `app/infrastructure/<adapter>.py`
- Utils: `app/utils/<topic>.py`

## What NOT to mix
- Do not write prompt text in `graph.py`, `services/`, or anywhere outside `app/prompts/`.
- Do not call `psycopg` outside `app/db.py`.
- Do not call `get_client()` directly from graph nodes — go through a service.
- Do not put business logic (parsing, seeding, decisions) in `infrastructure/` or `utils/`.

# TDD Rule

Before implementing any new function or changing existing logic:
1. Update (or write) the spec in `tests/specs/<domain>.md` — inputs, outputs, invariants, edge cases.
2. Write a failing test in `tests/unit/` (or `tests/integration/` if DB is involved).
3. Then implement the code.
4. Run `pytest tests/unit/` to confirm green before marking the task done.

**Run tests after every change**: `pytest tests/unit/` (fast, no Docker).  
Full suite including integration: `pytest` (requires Docker for testcontainers).

Never skip this cycle. A change that breaks an existing test must fix the test or explicitly update the spec — not delete the test.
