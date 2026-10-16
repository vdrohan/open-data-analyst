# Impact log

One entry per phase, written so an AI can turn it into a CV accomplishment statement (what was built, how it was measured, what the result was).

## Phase 0 - Scope and scaffold
- Scoped a natural-language analyst agent over Canadian housing data; chose stack and guardrails; set up CI, linting, secret scanning and a decisions log.
- Metrics: none yet.

## Phase 1 - Data layer and calculation tools (in progress)
- Built and tested the mortgage payment function (Canadian semi-annual compounding, validated by amortizing the loan to zero and against a known figure: $500,000 at 5% over 25 years is $2,908.02 a month) and the distance function that defines the 40 km scope.
- Built a repeatable ingest from three Canadian public sources into a DuckDB store: Bank of Canada posted 5-year mortgage rate (3,264 observations, 1973 to Oct 2026), Statistics Canada quarterly asking and paid rent by metropolitan area (9,646 rows, 2019 to Apr 2026), and CMHC new-home sales by price band and municipality (806,887 rows, 2016 to Aug 2026) parsed from 18 Excel workbooks, plus a 31-row municipality table that flags the municipalities within 40 km of downtown Vancouver (23 in scope, 4 of them borderline). One command refreshes everything.
- Found and documented source problems before they reached answers: the Bank of Canada series named in the plan stopped updating in 2019 (replaced with its weekly successor), CMHC publishes overlapping month, quarter and year files that would triple-count sales, and CMHC suppresses small counts. Cross-checks: band counts reconcile to published row totals except where cells are suppressed (29,027 rows match, 5,489 differ and every one contains a suppressed cell).
- Every table and column has a description stored in the database and rendered to docs/data-dictionary.md; a test fails if they drift apart.
- Metrics: 27 unit tests passing (parsers, scope rule, store build, dictionary currency).
