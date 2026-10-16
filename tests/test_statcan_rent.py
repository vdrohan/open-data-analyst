from datetime import date

from open_data_analyst.data.statcan_rent import parse_csv

HEADER = (
    '"REF_DATE","GEO","DGUID","Rental unit type","Estimates","UOM","UOM_ID","SCALAR_FACTOR",'
    '"SCALAR_ID","VECTOR","COORDINATE","VALUE","STATUS","SYMBOL","TERMINATED","DECIMALS"\n'
)


def row(value, status=""):
    return (
        '"2026-04","Vancouver, Census metropolitan area (CMA)","2021S0503933",'
        f'"Apartment - 2 bedrooms","Average asking rent","Dollars","81","units","0","v1",'
        f'"1.1.1","{value}","{status}","","","0"\n'
    )


def test_parses_value_and_quarter_start():
    (r,) = parse_csv("﻿" + HEADER + row("3030"))
    assert r.ref_date == date(2026, 4, 1)
    assert r.rent_dollars == 3030
    assert r.rental_unit_type == "Apartment - 2 bedrooms"


def test_unavailable_and_unreliable_values_become_null_but_caution_is_kept():
    rows = parse_csv(HEADER + row("", "..") + row("2500", "F") + row("2600", "E"))
    assert [r.rent_dollars for r in rows] == [None, None, 2600]
    assert [r.status for r in rows] == ["..", "F", "E"]
