"""Table definitions for the DuckDB store. Also the source of docs/data-dictionary.md.

Every table and column carries a description. They are written to the database as
comments so the agent (Phase 3) can read them with its schema-lookup tool.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str


@dataclass(frozen=True)
class Table:
    name: str
    description: str
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...] = ()


TABLES: tuple[Table, ...] = (
    Table(
        "boc_mortgage_rate",
        "Posted 5-year conventional mortgage rate from the Bank of Canada Valet API. These are "
        "posted rates (what banks advertise), usually above what a buyer is actually offered. "
        "Two series: V122521 (monthly, ends 2019-09-01, discontinued) and V80691335 (weekly, "
        "current). For today's rate use V80691335 and take the latest observation_date.",
        (
            Column(
                "series_id",
                "VARCHAR",
                "Valet series: 'V122521' (legacy monthly) or 'V80691335' (current weekly).",
            ),
            Column("frequency", "VARCHAR", "'monthly' or 'weekly'."),
            Column(
                "observation_date", "DATE", "Observation date (first of the month for monthly)."
            ),
            Column(
                "rate_pct",
                "DOUBLE",
                "Rate in percent per year, e.g. 6.19 means 6.19%. Divide by 100 for mortgage_payment().",
            ),
        ),
        ("series_id", "observation_date"),
    ),
    Table(
        "statcan_rent",
        "Statistics Canada table 46-10-0092-01: average asking rent (listings on rental "
        "platforms, what a new tenant would face) and average paid rent, by rental unit type. "
        "Quarterly, by census metropolitan area (CMA), experimental. Reports the whole CMA only; "
        "there is no municipality detail. Not every unit type or CMA has every quarter.",
        (
            Column(
                "ref_date",
                "DATE",
                "First day of the reference quarter's month (2026-04-01 = April 2026).",
            ),
            Column(
                "geo",
                "VARCHAR",
                "Geography, e.g. 'Vancouver, Census metropolitan area (CMA)'. 'All census metropolitan areas' is a national roll-up.",
            ),
            Column("dguid", "VARCHAR", "Statistics Canada geography id; empty for the roll-up."),
            Column(
                "rental_unit_type",
                "VARCHAR",
                "'Apartment - No bedroom', '... 1 bedroom', '... 2 bedrooms', '... 3 or more bedrooms', 'House - 2 bedrooms', 'House - 3 or more bedrooms', 'Room'.",
            ),
            Column("estimate", "VARCHAR", "'Average asking rent' or 'Average paid rent'."),
            Column(
                "rent_dollars",
                "INTEGER",
                "Monthly rent in dollars. NULL when Statistics Canada reports no figure or marks it too unreliable (status '..' or 'F').",
            ),
            Column(
                "status",
                "VARCHAR",
                "Statistics Canada flag: '' normal, 'E' use with caution, 'F' too unreliable to publish, '..' not available.",
            ),
            Column("vector", "VARCHAR", "Statistics Canada time-series id, for citing."),
        ),
        ("ref_date", "geo", "rental_unit_type", "estimate"),
    ),
    Table(
        "cmhc_absorbed_units",
        "CMHC Market Absorption Survey: newly built homes sold ('absorbed') by price band, "
        "dwelling type and municipality. One row per cell with a count. These are sale prices of "
        "new homes in bands, not a median or average price. Counts under 10 per geography have "
        "their price breakdown suppressed (suppressed = true, units NULL). Sum units across bands "
        "only for rows where suppressed is false and say the total may be understated. "
        "Periods are full years 2016-2025 plus single months of 2026 (see period_type).",
        (
            Column(
                "period_start",
                "DATE",
                "First day of the period: 2025-01-01 with period_type 'year' means calendar 2025; 2026-03-01 with 'month' means March 2026.",
            ),
            Column(
                "period_type",
                "VARCHAR",
                "'year' or 'month'. Never add a year row to month rows for the same year.",
            ),
            Column("cma", "VARCHAR", "Census metropolitan area name, e.g. 'Vancouver'."),
            Column(
                "csd_code",
                "VARCHAR",
                "7-digit Statistics Canada census subdivision code; join to municipality.csd_code. NULL on the CMA total row.",
            ),
            Column(
                "csd_name",
                "VARCHAR",
                "Municipality name as CMHC prints it. 'Vancouver CMA: Total' is the CMA total row. Names repeat across codes (two 'Langley'), so join on csd_code.",
            ),
            Column(
                "csd_type",
                "VARCHAR",
                "Census subdivision type: CY city, DM district municipality, VL village, IM island municipality, RDA electoral area, etc.",
            ),
            Column(
                "dwelling_type",
                "VARCHAR",
                "'single', 'semi' (semi-detached), 'row' (townhouse), 'apartment' (condo/apartment and other), or 'total' (all types).",
            ),
            Column(
                "band_label", "VARCHAR", "Price band as CMHC prints it, e.g. '700,000-749,999'."
            ),
            Column("price_low", "INTEGER", "Band lower bound in dollars (0 for the '<' band)."),
            Column(
                "price_high",
                "INTEGER",
                "Band upper bound in dollars; NULL for the open-ended top band.",
            ),
            Column("units", "INTEGER", "Homes sold in this band. NULL when suppressed."),
            Column("suppressed", "BOOLEAN", "True when CMHC withheld the count ('**')."),
        ),
    ),
    Table(
        "cmhc_absorbed_totals",
        "Row totals that go with cmhc_absorbed_units: homes sold with a known price ('priced') "
        "and without ('unpriced': owner-built singles and semis, and row and apartment units "
        "whose price is not available). Use this for unit counts; priced + unpriced = total.",
        (
            Column("period_start", "DATE", "As in cmhc_absorbed_units."),
            Column("period_type", "VARCHAR", "'year' or 'month'."),
            Column("cma", "VARCHAR", "Census metropolitan area name."),
            Column(
                "csd_code", "VARCHAR", "7-digit census subdivision code; NULL on the CMA total row."
            ),
            Column(
                "csd_name",
                "VARCHAR",
                "Municipality name; 'Vancouver CMA: Total' for the CMA total row.",
            ),
            Column("csd_type", "VARCHAR", "Census subdivision type."),
            Column("dwelling_type", "VARCHAR", "'single', 'semi', 'row', 'apartment' or 'total'."),
            Column(
                "priced", "INTEGER", "Units with a price in a band. NULL when CMHC gave no figure."
            ),
            Column("unpriced", "INTEGER", "Units with no price on record."),
            Column("total", "INTEGER", "priced + unpriced."),
        ),
    ),
    Table(
        "municipality",
        "British Columbia municipalities near Vancouver with their distance from Waterfront "
        "Station (49.2858 N, 123.1117 W) and the scope flag (decision 8: in scope when within "
        "40 km straight-line). Distance is to one reference point per municipality (the named "
        "city, town or village centre), not to its nearest edge, and is straight-line, not "
        "road distance. Includes municipalities slightly beyond 40 km for context. Canadian "
        "municipalities only. The data tables mostly report the whole Vancouver CMA, so this "
        "table says which municipalities the agent may name, not which rows exist.",
        (
            Column(
                "csd_code",
                "VARCHAR",
                "7-digit Statistics Canada census subdivision code (2016 boundaries); joins to cmhc_* tables.",
            ),
            Column(
                "name",
                "VARCHAR",
                "Municipality name. Two municipalities can share a name (Langley, North Vancouver); csd_type tells them apart.",
            ),
            Column(
                "csd_type",
                "VARCHAR",
                "CY city, T town, VL village, DM district municipality, IM island municipality, RDA electoral area.",
            ),
            Column("kind", "VARCHAR", "'municipality' or 'electoral_area'."),
            Column(
                "population",
                "INTEGER",
                "Latest Statistics Canada July population estimate (table 17-10-0142-01).",
            ),
            Column("population_year", "INTEGER", "Year of that estimate."),
            Column("latitude", "DOUBLE", "Reference point latitude."),
            Column("longitude", "DOUBLE", "Reference point longitude."),
            Column(
                "point_source",
                "VARCHAR",
                "Where the reference point came from: 'cgns:<record type>:<id>' (Natural Resources Canada place names) or a stated manual choice.",
            ),
            Column(
                "distance_km",
                "DOUBLE",
                "Straight-line kilometres from Waterfront Station to the reference point.",
            ),
            Column("in_scope", "BOOLEAN", "True when distance_km <= 40."),
            Column(
                "borderline",
                "BOOLEAN",
                "True when distance_km is within 3 km of the 40 km cut-off, so the call is close.",
            ),
        ),
        ("csd_code",),
    ),
    Table(
        "ingest_log",
        "Provenance of each raw file in the last build: where it came from, when, and its "
        "checksum. Cite source_url and fetched_at when stating where a number comes from.",
        (
            Column(
                "source", "VARCHAR", "Source key: boc, statcan_rent, cmhc_absorbed, municipalities."
            ),
            Column("source_url", "VARCHAR", "Exact URL downloaded."),
            Column("file", "VARCHAR", "Local file name under data/raw/<source>/."),
            Column("sha256", "VARCHAR", "SHA-256 of the downloaded file."),
            Column("fetched_at", "TIMESTAMP", "UTC time of download."),
        ),
    ),
)


def ddl(table: Table) -> str:
    cols = [f"{c.name} {c.type}" for c in table.columns]
    if table.primary_key:
        cols.append(f"PRIMARY KEY ({', '.join(table.primary_key)})")
    return f"CREATE TABLE {table.name} ({', '.join(cols)})"


def _escape(text: str) -> str:
    return text.replace("'", "''")


def comment_statements(table: Table) -> list[str]:
    out = [f"COMMENT ON TABLE {table.name} IS '{_escape(table.description)}'"]
    out += [
        f"COMMENT ON COLUMN {table.name}.{c.name} IS '{_escape(c.description)}'"
        for c in table.columns
    ]
    return out


def dictionary_markdown() -> str:
    """Render docs/data-dictionary.md. A test keeps the committed file in step."""
    lines = [
        "# Data dictionary",
        "",
        "Generated from `src/open_data_analyst/data/schema.py` by "
        "`uv run python -m open_data_analyst.data dictionary`. Do not edit by hand.",
        "",
    ]
    for table in TABLES:
        lines += [f"## {table.name}", "", table.description, ""]
        lines += ["| Column | Type | Meaning |", "|---|---|---|"]
        lines += [f"| `{c.name}` | {c.type} | {c.description} |" for c in table.columns]
        if table.primary_key:
            lines += ["", f"Unique on: {', '.join(table.primary_key)}."]
        lines.append("")
    return "\n".join(lines)
