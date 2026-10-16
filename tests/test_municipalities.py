import json

from open_data_analyst.data.municipalities import (
    build,
    choose_point,
    parse_cgns,
    parse_population,
)

HEADER = (
    '"REF_DATE","GEO","DGUID","UOM","UOM_ID","SCALAR_FACTOR","SCALAR_ID","VECTOR",'
    '"COORDINATE","VALUE","STATUS","SYMBOL","TERMINATED","DECIMALS"\n'
)


def _pop(year, geo, dguid, value):
    return (
        f'"{year}","{geo}","{dguid}","Persons","249","units","0","v","1","{value}","","","","0"\n'
    )


POPULATION = (
    HEADER
    + _pop(2021, "Langley (DM), British Columbia", "2016A00055915001", 140000)
    + _pop(2022, "Langley (DM), British Columbia", "2016A00055915001", 142043)
    + _pop(2022, "Langley (CY), British Columbia", "2016A00055915002", 30084)
    + _pop(2022, "Squamish (DM), British Columbia", "2016A00055931006", 23652)
    + _pop(2022, "Capilano 5 (IRI), British Columbia", "2016A00055915808", 3386)
    + _pop(2022, "Toronto (C), Ontario", "2016A00053520005", 2900000)
)


def _cgns(concise, *items):
    return json.dumps(
        {"items": [{"name": n, "id": i, "latitude": la, "longitude": lo} for n, i, la, lo in items]}
    )


CGNS = {
    "CITY": _cgns("CITY", ("Langley", "AAA", 49.1044, -122.6608)),
    "MUN1": _cgns("MUN1", ("Langley", "BBB", 49.10, -122.68), ("Squamish", "CCC", 49.70, -123.15)),
    "MUN2": _cgns("MUN2", ("Squamish", "DDD", 49.31, -123.10)),  # a lookalike in North Vancouver
}


def test_population_keeps_latest_year_and_only_bc():
    pop = parse_population(POPULATION)
    assert pop["5915001"] == ("Langley", "DM", 142043, 2022)
    assert "3520005" not in pop and "5915808" in pop  # reserves are parsed, filtered later


def test_district_and_city_with_the_same_name_get_different_points():
    records = parse_cgns(CGNS)["Langley"]
    assert choose_point(records, "area")["id"] == "BBB"
    assert choose_point(records, "named_place")["id"] == "AAA"


def test_build_scopes_by_distance_and_skips_reserves():
    rows = {m.csd_code: m for m in build(parse_population(POPULATION), parse_cgns(CGNS))}
    assert set(rows) == {"5915001", "5915002", "5931006"}  # reserve dropped
    assert rows["5915001"].in_scope and rows["5915001"].borderline
    assert rows["5915001"].point_source == "cgns:MUN1:BBB"
    assert rows["5915002"].point_source == "cgns:CITY:AAA"
    squamish = rows["5931006"]
    assert squamish.point_source == "cgns:MUN1:CCC"  # not the MUN2 lookalike in North Vancouver
    assert not squamish.in_scope and not squamish.borderline and squamish.distance_km > 40
