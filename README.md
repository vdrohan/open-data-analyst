# open-data-analyst

Ask a question about Canadian housing in plain English. A Claude agent writes read-only SQL against a local DuckDB store, runs it, and returns the number, a chart and the exact query, or says it can't answer.

**Status: Phase 0 (scaffold and plan).** Nothing is built yet. See [docs/plan.md](docs/plan.md).

## Why this exists
Second portfolio project. Where [support-desk-assistant](https://github.com/vdrohan/support-desk-assistant) answers from documents, this one answers from structured data using tools, and is judged on exact numbers against an eval set.

## Layout
- `src/open_data_analyst/data` - ingest, schema, data dictionary (Phase 1)
- `src/open_data_analyst/agent` - Claude tool loop with read-only SQL guardrails (Phase 3)
- `src/open_data_analyst/evals` - eval set and scoring runner (Phase 2)
- `docs/` - plan, decisions log, per-phase impact notes

## Development
```
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run pre-commit install
```
