# CLAUDE.md

Python 3.12, uv, src layout (`src/open_data_analyst`). Run `uv run ruff check . && uv run ruff format --check . && uv run pytest` before committing.

## Rules
- Evals come before the agent: no agent code until the eval runner can score a baseline.
- The agent's SQL must be read-only with row and time limits; never give it write access to the DuckDB store.
- Every answer shows its query; the agent abstains rather than guess.
- Cloud-only AI (Claude). Default to Haiku for the agent loop; log cost per question.
- Never commit secrets or raw data (`data/raw/` and `*.duckdb` are gitignored).
- Log decisions in `docs/decisions.md` and per-phase accomplishments in `docs/impact.md`, written so they can be turned into CV statements.
- The owner wants options with pros and cons at each decision, and reasoning for any better alternative.
