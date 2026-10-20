# open-data-analyst

Ask a question about Canadian housing in plain English. A Claude agent writes read-only SQL against a local DuckDB store, runs it, and returns the number, a chart and the exact query, or says it can't answer.

**Status: Phase 3 (agent core).** The data layer works, a 41-question eval set with a scorer exists, and the agent scored 100% on three consecutive live runs (0 confident-wrong) against a 29% always-abstain floor, at about $0.002 per question. The set was tuned against its own failures, so fresh questions are the next check. See [docs/plan.md](docs/plan.md) and [docs/data-dictionary.md](docs/data-dictionary.md).

## Why this exists
Second portfolio project. Where [support-desk-assistant](https://github.com/vdrohan/support-desk-assistant) answers from documents, this one answers from structured data using tools, and is judged on exact numbers against an eval set.

## Layout
- `src/open_data_analyst/data` - ingest, schema, data dictionary (Phase 1)
  - `uv run python -m open_data_analyst.data refresh` downloads the sources to `data/raw/` and builds `data/open_data.duckdb` (both gitignored)
- `src/open_data_analyst/agent` - Claude tool loop with read-only SQL guardrails (Phase 3)
- `src/open_data_analyst/evals` - eval set and scoring runner (Phase 2)
  - `uv run python -m open_data_analyst.evals verify` re-derives every expected answer from the data; `baseline` scores the always-abstain floor
  - `agent` scores the Claude agent on the set (needs `ANTHROPIC_API_KEY`; `--max-cost` caps spend, default $1; traces go to `data/eval/runs/`)
  - questions live in `data/eval/questions.jsonl`
- `docs/` - plan, decisions log, per-phase impact notes

## Development
```
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run pre-commit install
```
