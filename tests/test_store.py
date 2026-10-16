import dataclasses
import json
import zipfile
from pathlib import Path

import duckdb

from open_data_analyst.data import boc, cmhc, municipalities, schema, statcan_rent, store
from tests.test_municipalities import CGNS, POPULATION
from tests.test_statcan_rent import HEADER as RENT_HEADER
from tests.test_statcan_rent import row as rent_row

VALET = '"OBSERVATIONS"\n"date","{s}"\n"2026-10-14","6.19"\n'


def _write_raw(raw: Path) -> None:
    (raw / "boc").mkdir(parents=True)
    for series in boc.SERIES:
        (raw / "boc" / f"{series}.csv").write_text(VALET.format(s=series))
    (raw / "statcan_rent").mkdir()
    with zipfile.ZipFile(raw / "statcan_rent" / f"{statcan_rent.PID}-eng.zip", "w") as z:
        z.writestr(f"{statcan_rent.PID}.csv", RENT_HEADER + rent_row("3030"))
    (raw / "municipalities").mkdir()
    with zipfile.ZipFile(raw / "municipalities" / f"{municipalities.POP_PID}-eng.zip", "w") as z:
        z.writestr(f"{municipalities.POP_PID}.csv", POPULATION)
    for code in municipalities.CGNS_CODES:
        (raw / "municipalities" / f"cgns-{code}.json").write_text(
            CGNS.get(code, json.dumps({"items": []}))
        )
    (raw / "cmhc_absorbed").mkdir()


def test_schema_columns_match_the_row_types():
    rows = {
        "boc_mortgage_rate": boc.RateObservation,
        "statcan_rent": statcan_rent.RentObservation,
        "cmhc_absorbed_units": cmhc.BandCount,
        "cmhc_absorbed_totals": cmhc.UnitTotals,
        "municipality": municipalities.Municipality,
    }
    tables = {t.name: t for t in schema.TABLES}
    for name, row_type in rows.items():
        assert [c.name for c in tables[name].columns] == [
            f.name for f in dataclasses.fields(row_type)
        ], name


def test_build_loads_every_table_and_comments_them(tmp_path):
    raw = tmp_path / "raw"
    _write_raw(raw)
    db = tmp_path / "out" / "test.duckdb"
    counts = store.build(raw, db)
    assert counts["boc_mortgage_rate"] == 2
    assert counts["statcan_rent"] == 1
    assert counts["municipality"] == 3
    assert counts["cmhc_absorbed_units"] == 0

    con = duckdb.connect(str(db), read_only=True)
    comment = con.execute(
        "SELECT comment FROM duckdb_tables() WHERE table_name = 'statcan_rent'"
    ).fetchone()[0]
    assert "asking rent" in comment
    langley = con.execute(
        "SELECT in_scope, borderline FROM municipality WHERE csd_code = '5915001'"
    ).fetchone()
    assert langley == (True, True)
    con.close()
    assert store.check(db) == []


def test_data_dictionary_file_is_current():
    committed = Path("docs/data-dictionary.md").read_text()
    assert committed == schema.dictionary_markdown(), (
        "run: uv run python -m open_data_analyst.data dictionary"
    )
