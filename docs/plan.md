# Plan: housing data analyst agent

Draft 2026-10-16. Ask a question about Canadian housing in plain English; a Claude agent writes read-only SQL, runs it, and returns the number, a chart and the query, or abstains.

## Goals
Show agents and tool use over structured data, a second language (TypeScript), and a deployed, observable service. Reuses the earlier support-desk project's habits: eval set first, show-your-work answers, CI, decisions log, impact log.

## Assumptions
- Cloud-only AI; Haiku for the agent loop; spend capped.
- DuckDB on a modest laptop, not a server database.
- Client is the owner. Sources are public housing data (Statistics Canada, CMHC, possibly provincial). Exact tables are confirmed in Phase 1; none are assumed yet.

## Phases
| # | Phase | Output | Done when | Status |
|---|---|---|---|---|
| 0 | Scope + scaffold | This plan, repo, CI | PR merged | Done |
| 1 | Data layer | 3-5 housing tables in DuckDB, data dictionary, refresh script, source and licence notes | The owner's real questions are answerable by hand with SQL | Done |
| 2 | Eval set first | 40-60 questions with exact expected numbers, including unanswerable ones | Runner scores a baseline | Done |
| 3 | Agent core | Claude tool loop: schema lookup, read-only SQL with row/time limits, query shown, abstains when unsure | Beats baseline, guardrail tests pass | Done (tuned set 100%, holdout 91%) |
| 4 | Charts + MCP | Chart output; tools wrapped as an MCP server | Works end to end from Claude Desktop | Next |
| 5 | TypeScript UI + deploy | Small web UI behind Tailscale or Cloudflare Tunnel, logging, cost tracking | Used daily on real questions | Not started |
| 6 | Write-up | Eval results, cost per question, limits | docs/impact.md complete | Not started |

If time gets tight, cut the Phase 5 UI first and keep the evals.

## Risks
- Housing sources differ in geography codes and release schedules: budget real time in Phase 1.
- Agent loops cost more tokens than single calls: step cap, Haiku, cost logged.
- Text-to-SQL demos are common: differentiate with the eval set, guardrails and honest abstention.
- A wrong but confident number is the worst failure: showing the query and abstaining are mandatory.

## Open questions
1. Which 3-5 tables first (Phase 1 starts with a source survey and licence check)?
2. Public repo from the start, or private until Phase 2?
