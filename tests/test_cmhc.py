from datetime import date

import openpyxl
import pytest

from open_data_analyst.data.cmhc import (
    parse_band,
    parse_workbook,
    select_editions,
    split_csd,
)


def test_parse_band_variants():
    assert parse_band("<299,999").high == 299_999 and parse_band("<299,999").low == 0
    band = parse_band("700,000-749,999")
    assert (band.low, band.high) == (700_000, 749_999)
    top = parse_band("4,000,000+")
    assert (top.low, top.high) == (4_000_000, None)
    with pytest.raises(ValueError):
        parse_band("Priced")


def test_split_csd():
    assert split_csd("(5915004) Surrey CY") == ("5915004", "Surrey", "CY")
    assert split_csd("(5915046) North Vancouver DM") == ("5915046", "North Vancouver", "DM")
    assert split_csd("Vancouver CMA: Total") == (None, "Vancouver CMA: Total", None)


def test_select_editions_takes_years_and_only_months_of_unfinished_years():
    editions = [
        {"Editions": "August 2026", "Itemid": "a"},
        {"Editions": "Q2 2026", "Itemid": "b"},
        {"Editions": "January 2026", "Itemid": "c"},
        {"Editions": "January – December 2025", "Itemid": "d"},
        {"Editions": "December 2025", "Itemid": "e"},
        {"Editions": "Q4 2025", "Itemid": "f"},
    ]
    chosen = select_editions(editions)
    assert [(e.period_type, e.period_start) for e in chosen] == [
        ("year", date(2025, 1, 1)),
        ("month", date(2026, 1, 1)),
        ("month", date(2026, 8, 1)),
    ]
    assert chosen[0].file_stem == "cma-2025" and chosen[1].file_stem == "cma-2026-01"


def _workbook(tmp_path):
    path = tmp_path / "cma-2025.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vancouver"
    ws.append(["Absorbed Homeowner and Condominium Units ... (2025)"])
    ws.append(["Vancouver Census Metropolitan Area (CMA)"])
    ws.append([None])
    ws.append(["Vancouver CMA", 2025, "Price Range ($)"])
    ws.append(
        ["Census Subdivision", "Dwelling Type", "<299,999", "300,000-349,999", "350,000+",
         "Priced", "Unpriced", "Total"]
    )  # fmt: skip
    ws.append(["(5915004) Surrey CY", "Absorbed - Single", 1, 0, 2, 3, 1, 4])
    ws.append(["(5915004) Surrey CY", "Absorbed - Semi-Detached", "**", "**", "**", 12, 0, 12])
    ws.append(["(5915004) Surrey CY", "Absorbed - Row", 0, 0, 0, 0, 0, 0])
    ws.append(["(5915004) Surrey CY", "Absorbed - Apartment and other", 5, 6, 7, 18, 0, 18])
    ws.append(["(5915004) Surrey CY", "Total", " ", " ", " ", 33, 1, 34])
    ws.append(["Vancouver CMA: Total", "Total", " ", " ", " ", 33, 1, 34])
    ws.append(["Note:"])
    ws.append(["1. Price Range data is suppressed ..."])
    wb.save(path)
    return path


def test_parse_workbook(tmp_path):
    counts, totals = parse_workbook(_workbook(tmp_path), date(2025, 1, 1), "year")

    apartment = [c for c in counts if c.dwelling_type == "apartment"]
    assert [(c.band_label, c.units) for c in apartment] == [
        ("<299,999", 5), ("300,000-349,999", 6), ("350,000+", 7),
    ]  # fmt: skip
    assert apartment[0].price_low == 0 and apartment[0].price_high == 299_999
    assert apartment[2].price_high is None

    semi = [c for c in counts if c.dwelling_type == "semi"]
    assert len(semi) == 3 and all(c.suppressed and c.units is None for c in semi)

    assert not [c for c in counts if c.dwelling_type == "total"]  # blank band cells carry nothing
    assert {c.cma for c in counts} == {"Vancouver"}
    assert {c.csd_code for c in counts} == {"5915004"}

    by_type = {(t.csd_code, t.dwelling_type): t for t in totals}
    assert by_type[("5915004", "single")].total == 4
    assert by_type[("5915004", "total")].unpriced == 1
    cma_total = by_type[(None, "total")]
    assert cma_total.csd_name == "Vancouver CMA: Total" and cma_total.total == 34
    assert len(totals) == 6
