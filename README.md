# open-data-analyst

Ask a question about Canadian housing in plain English. A Claude agent writes read-only SQL against a local DuckDB store, runs it, and returns the number, a chart and the exact query, or says it can't answer.

**Status: Phase 2 (eval set).** The data layer works and a first 41-question eval set with a scorer exists; the agent is not built yet. See [docs/plan.md](docs/plan.md) and [docs/data-dictionary.md](docs/data-dictionary.md).

## Why this exists
Second portfolio project. Where [support-desk-assistant](https://github.com/vdrohan/support-desk-assistant) answers from documents, this one answers from structured data using tools, and is judged on exact numbers against an eval set.

## Layout
- `src/open_data_analyst/data` - ingest, schema, data dictionary (Phase 1)
  - `uv run python -m open_data_analyst.data refresh` downloads the sources to `data/raw/` and builds `data/open_data.duckdb` (both gitignored)
- `src/open_data_analyst/agent` - Claude tool loop with read-only SQL guardrails (Phase 3)
- `src/open_data_analyst/evals` - eval set and scoring runner (Phase 2)
  - `uv run python -m open_data_analyst.evals verify` re-derives every expected answer from the data; `baseline` scores the always-abstain floor
  - questions live in `data/eval/questions.jsonl`
- `docs/` - plan, decisions log, per-phase impact notes

## Development
```
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run pre-commit install
```
