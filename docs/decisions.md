# Decisions

Format: number, date, decision, reasoning.

1. 2026-10-16 - Project is an open-data analyst agent, not a server-ops agent or workflow tool. Fills the gaps project 1 leaves (agents/tool use, structured data) that Forward Deployed Engineer postings ask for.
2. 2026-10-16 - Theme is Canadian housing (starts, rents, prices), chosen over labour market + CPI, federal spending and demographics. Relevant to the owner's Vancouver/Surrey move, and the owner is the "client" asking the questions. Trade-off: housing data comes from several sources with inconsistent geography codes, so Phase 1 is slower.
3. 2026-10-16 - Client is the owner (as in project 1). Revisit adding an outside client after Phase 3 if one is available.
4. 2026-10-16 - DuckDB as the store (no server process, light on the 2017 Air's RAM). Postgres only if a later need appears.
5. 2026-10-16 - Cloud-only AI; Claude Haiku for the agent loop by default, with a step cap and per-question cost logging.
6. 2026-10-16 - Repo stays private until the eval set exists (Phase 2).
7. 2026-10-16 - Question focus is monthly cost: rent versus mortgage payment on a new property. Mortgage payment will be a calculator tool (Canadian semi-annual compounding), not a table lookup, so answers stay exactly checkable. Source survey in the project files (phase1-source-survey.md); assumptions for down payment and amortization still to be set.
8. 2026-10-16 - Scope is every municipality within 40 km of downtown Vancouver and all dwelling types (house, condo, apartment, townhouse). The owner chose a distance rule over commute time, so membership is computed, not judged: a reference table of municipalities with centroid coordinates, straight-line distance from a fixed downtown point (Waterfront Station, about 49.2858 N, 123.1117 W), and an in-scope flag. Straight-line, not road distance; the choice is stated in answers. Where a source only reports the Vancouver CMA or lacks a dwelling type, the agent must say so rather than infer.
9. 2026-10-16 - Calculator defaults confirmed by the owner: 20% down, 25-year amortization, as parameters. Not financial advice; insured-mortgage rules to be checked.
