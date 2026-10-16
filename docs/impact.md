# Impact log

One entry per phase, written so an AI can turn it into a CV accomplishment statement (what was built, how it was measured, what the result was).

## Phase 0 - Scope and scaffold
- Scoped a natural-language analyst agent over Canadian housing data; chose stack and guardrails; set up CI, linting, secret scanning and a decisions log.
- Metrics: none yet.

## Phase 1 - Calculation tools (in progress)
- Built and tested the mortgage payment function (Canadian semi-annual compounding, validated by amortizing the loan to zero and against a known figure: $500,000 at 5% over 25 years is $2,908.02 a month) and the distance function that defines the 40 km scope.
- Metrics: 13 unit tests. Data ingest not started: the session's network policy blocks statcan.gc.ca and bankofcanada.ca.
