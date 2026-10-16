# Decisions

Format: number, date, decision, reasoning.

1. 2026-10-16 - Project is an open-data analyst agent, not a server-ops agent or workflow tool. Fills the gaps project 1 leaves (agents/tool use, structured data) that Forward Deployed Engineer postings ask for.
2. 2026-10-16 - Theme is Canadian housing (starts, rents, prices), chosen over labour market + CPI, federal spending and demographics. Relevant to the owner's Vancouver/Surrey move, and the owner is the "client" asking the questions. Trade-off: housing data comes from several sources with inconsistent geography codes, so Phase 1 is slower.
3. 2026-10-16 - Client is the owner (as in project 1). Revisit adding an outside client after Phase 3 if one is available.
4. 2026-10-16 - DuckDB as the store (no server process, light on the 2017 Air's RAM). Postgres only if a later need appears.
5. 2026-10-16 - Cloud-only AI; Claude Haiku for the agent loop by default, with a step cap and per-question cost logging.
