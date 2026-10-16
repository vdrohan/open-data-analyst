# Data dictionary

Generated from `src/open_data_analyst/data/schema.py` by `uv run python -m open_data_analyst.data dictionary`. Do not edit by hand.

## boc_mortgage_rate

Posted 5-year conventional mortgage rate from the Bank of Canada Valet API. These are posted rates (what banks advertise), usually above what a buyer is actually offered. Two series: V122521 (monthly, ends 2019-09-01, discontinued) and V80691335 (weekly, current). For today's rate use V80691335 and take the latest observation_date.

| Column | Type | Meaning |
|---|---|---|
| `series_id` | VARCHAR | Valet series: 'V122521' (legacy monthly) or 'V80691335' (current weekly). |
| `frequency` | VARCHAR | 'monthly' or 'weekly'. |
| `observation_date` | DATE | Observation date (first of the month for monthly). |
| `rate_pct` | DOUBLE | Rate in percent per year, e.g. 6.19 means 6.19%. Divide by 100 for mortgage_payment(). |

Unique on: series_id, observation_date.

## statcan_rent

Statistics Canada table 46-10-0092-01: average asking rent (listings on rental platforms, what a new tenant would face) and average paid rent, by rental unit type. Quarterly, by census metropolitan area (CMA), experimental. Reports the whole CMA only; there is no municipality detail. Not every unit type or CMA has every quarter.

| Column | Type | Meaning |
|---|---|---|
| `ref_date` | DATE | First day of the reference quarter's month (2026-04-01 = April 2026). |
| `geo` | VARCHAR | Geography, e.g. 'Vancouver, Census metropolitan area (CMA)'. 'All census metropolitan areas' is a national roll-up. |
| `dguid` | VARCHAR | Statistics Canada geography id; empty for the roll-up. |
| `rental_unit_type` | VARCHAR | 'Apartment - No bedroom', '... 1 bedroom', '... 2 bedrooms', '... 3 or more bedrooms', 'House - 2 bedrooms', 'House - 3 or more bedrooms', 'Room'. |
| `estimate` | VARCHAR | 'Average asking rent' or 'Average paid rent'. |
| `rent_dollars` | INTEGER | Monthly rent in dollars. NULL when Statistics Canada reports no figure or marks it too unreliable (status '..' or 'F'). |
| `status` | VARCHAR | Statistics Canada flag: '' normal, 'E' use with caution, 'F' too unreliable to publish, '..' not available. |
| `vector` | VARCHAR | Statistics Canada time-series id, for citing. |

Unique on: ref_date, geo, rental_unit_type, estimate.

## cmhc_absorbed_units

CMHC Market Absorption Survey: newly built homes sold ('absorbed') by price band, dwelling type and municipality. One row per cell with a count. These are sale prices of new homes in bands, not a median or average price. Counts under 10 per geography have their price breakdown suppressed (suppressed = true, units NULL). Sum units across bands only for rows where suppressed is false and say the total may be understated. Periods are full years 2016-2025 plus single months of 2026 (see period_type).

| Column | Type | Meaning |
|---|---|---|
| `period_start` | DATE | First day of the period: 2025-01-01 with period_type 'year' means calendar 2025; 2026-03-01 with 'month' means March 2026. |
| `period_type` | VARCHAR | 'year' or 'month'. Never add a year row to month rows for the same year. |
| `cma` | VARCHAR | Census metropolitan area name, e.g. 'Vancouver'. |
| `csd_code` | VARCHAR | 7-digit Statistics Canada census subdivision code; join to municipality.csd_code. NULL on the CMA total row. |
| `csd_name` | VARCHAR | Municipality name as CMHC prints it. 'Vancouver CMA: Total' is the CMA total row. Names repeat across codes (two 'Langley'), so join on csd_code. |
| `csd_type` | VARCHAR | Census subdivision type: CY city, DM district municipality, VL village, IM island municipality, RDA electoral area, etc. |
| `dwelling_type` | VARCHAR | 'single', 'semi' (semi-detached), 'row' (townhouse), 'apartment' (condo/apartment and other), or 'total' (all types). |
| `band_label` | VARCHAR | Price band as CMHC prints it, e.g. '700,000-749,999'. |
| `price_low` | INTEGER | Band lower bound in dollars (0 for the '<' band). |
| `price_high` | INTEGER | Band upper bound in dollars; NULL for the open-ended top band. |
| `units` | INTEGER | Homes sold in this band. NULL when suppressed. |
| `suppressed` | BOOLEAN | True when CMHC withheld the count ('**'). |

## cmhc_absorbed_totals

Row totals that go with cmhc_absorbed_units: homes sold with a known price ('priced') and without ('unpriced': owner-built singles and semis, and row and apartment units whose price is not available). Use this for unit counts; priced + unpriced = total.

| Column | Type | Meaning |
|---|---|---|
| `period_start` | DATE | As in cmhc_absorbed_units. |
| `period_type` | VARCHAR | 'year' or 'month'. |
| `cma` | VARCHAR | Census metropolitan area name. |
| `csd_code` | VARCHAR | 7-digit census subdivision code; NULL on the CMA total row. |
| `csd_name` | VARCHAR | Municipality name; 'Vancouver CMA: Total' for the CMA total row. |
| `csd_type` | VARCHAR | Census subdivision type. |
| `dwelling_type` | VARCHAR | 'single', 'semi', 'row', 'apartment' or 'total'. |
| `priced` | INTEGER | Units with a price in a band. NULL when CMHC gave no figure. |
| `unpriced` | INTEGER | Units with no price on record. |
| `total` | INTEGER | priced + unpriced. |

## municipality

British Columbia municipalities near Vancouver with their distance from Waterfront Station (49.2858 N, 123.1117 W) and the scope flag (decision 8: in scope when within 40 km straight-line). Distance is to one reference point per municipality (the named city, town or village centre), not to its nearest edge, and is straight-line, not road distance. Includes municipalities slightly beyond 40 km for context. Canadian municipalities only. The data tables mostly report the whole Vancouver CMA, so this table says which municipalities the agent may name, not which rows exist.

| Column | Type | Meaning |
|---|---|---|
| `csd_code` | VARCHAR | 7-digit Statistics Canada census subdivision code (2016 boundaries); joins to cmhc_* tables. |
| `name` | VARCHAR | Municipality name. Two municipalities can share a name (Langley, North Vancouver); csd_type tells them apart. |
| `csd_type` | VARCHAR | CY city, T town, VL village, DM district municipality, IM island municipality, RDA electoral area. |
| `kind` | VARCHAR | 'municipality' or 'electoral_area'. |
| `population` | INTEGER | Latest Statistics Canada July population estimate (table 17-10-0142-01). |
| `population_year` | INTEGER | Year of that estimate. |
| `latitude` | DOUBLE | Reference point latitude. |
| `longitude` | DOUBLE | Reference point longitude. |
| `point_source` | VARCHAR | Where the reference point came from: 'cgns:<record type>:<id>' (Natural Resources Canada place names) or a stated manual choice. |
| `distance_km` | DOUBLE | Straight-line kilometres from Waterfront Station to the reference point. |
| `in_scope` | BOOLEAN | True when distance_km <= 40. |
| `borderline` | BOOLEAN | True when distance_km is within 3 km of the 40 km cut-off, so the call is close. |

Unique on: csd_code.

## ingest_log

Provenance of each raw file in the last build: where it came from, when, and its checksum. Cite source_url and fetched_at when stating where a number comes from.

| Column | Type | Meaning |
|---|---|---|
| `source` | VARCHAR | Source key: boc, statcan_rent, cmhc_absorbed, municipalities. |
| `source_url` | VARCHAR | Exact URL downloaded. |
| `file` | VARCHAR | Local file name under data/raw/<source>/. |
| `sha256` | VARCHAR | SHA-256 of the downloaded file. |
| `fetched_at` | TIMESTAMP | UTC time of download. |
