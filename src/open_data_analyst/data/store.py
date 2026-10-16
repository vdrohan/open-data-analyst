"""Build the DuckDB store from the raw downloads. Rebuilt from scratch every time."""

import csv
import dataclasses
import tempfile
from pathlib import Path

import duckdb

from open_data_analyst.data import boc, cmhc, municipalities, schema, statcan_rent
from open_data_analyst.data.http import Fetched

DEFAULT_DB = Path("data/open_data.duckdb")


def _insert(con: duckdb.DuckDBPyConnection, table: str, rows: list) -> None:
    """Bulk-load dataclass rows through a temporary CSV (executemany is far too slow here)."""
    if not rows:
        return
    fields = [f.name for f in dataclasses.fields(rows[0])]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for row in rows:
                writer.writerow(["" if (v := getattr(row, f)) is None else v for f in fields])
        con.execute(
            f"COPY {table} ({', '.join(fields)}) FROM '{path}' "
            "(FORMAT csv, HEADER false, NULLSTR '')"
        )


def build(raw: Path, db_path: Path, provenance: list[Fetched] | None = None) -> dict[str, int]:
    """Create `db_path` fresh from the files under `raw`. Returns row counts per table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for table in schema.TABLES:
            con.execute(schema.ddl(table))
        counts, totals = cmhc.load(raw)
        _insert(con, "boc_mortgage_rate", boc.load(raw))
        _insert(con, "statcan_rent", statcan_rent.load(raw))
        _insert(con, "cmhc_absorbed_units", counts)
        _insert(con, "cmhc_absorbed_totals", totals)
        _insert(con, "municipality", municipalities.load(raw))
        for item in provenance or []:
            con.execute(
                "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?)",
                [item.source, item.url, item.path.name, item.sha256, item.fetched_at],
            )
        for table in schema.TABLES:
            for statement in schema.comment_statements(table):
                con.execute(statement)
        return {
            t.name: con.execute(f"SELECT count(*) FROM {t.name}").fetchone()[0]
            for t in schema.TABLES
        }
    finally:
        con.close()


def check(db_path: Path) -> list[str]:
    """Cross-table checks that catch silent gaps. Returns human-readable problems."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        problems = []
        missing = con.execute(
            """
            SELECT DISTINCT t.cma, t.csd_code, t.csd_name
            FROM cmhc_absorbed_totals t
            LEFT JOIN municipality m USING (csd_code)
            WHERE t.cma IN ('Vancouver', 'Abbotsford-Mission')
              AND t.csd_code IS NOT NULL AND m.csd_code IS NULL
              AND t.csd_code NOT LIKE '%999'  -- CMHC's First Nations roll-up, not a municipality
            ORDER BY 1, 2
            """
        ).fetchall()
        for cma, code, name in missing:
            problems.append(f"CMHC {cma} municipality {code} {name} has no row in municipality")
        latest = con.execute(
            "SELECT max(observation_date) FROM boc_mortgage_rate WHERE series_id = 'V80691335'"
        ).fetchone()[0]
        if latest is None:
            problems.append("no current Bank of Canada rate loaded")
        return problems
    finally:
        con.close()
