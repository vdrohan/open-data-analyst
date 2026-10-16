"""Municipality reference table: which British Columbia municipalities are within scope.

Decision 8: a municipality is in scope when its reference point is within 40 km,
straight-line, of Waterfront Station. Membership is computed, never judged.

Sources
- Municipality list and population: Statistics Canada table 17-10-0142-01 (2016
  census boundaries; codes match the 7-digit codes in CMHC's workbooks).
- Reference points: Natural Resources Canada's Canadian Geographical Names Service
  (CGNS). It has no single "centre of this municipality" field, so the point is the
  CGNS record of the municipality's own name, chosen by a fixed priority (see
  `choose_point`). The point is where people live (the named city, town or village
  centre), not the centroid of the legal boundary: a boundary centroid would drop
  large, mostly empty districts such as Maple Ridge.
- Municipalities whose point sits within BORDERLINE_KM of the cut-off are flagged
  so an answer can say the call is close.
"""

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from open_data_analyst.data.http import Fetched, download
from open_data_analyst.geo import SCOPE_RADIUS_KM, WATERFRONT_STATION, haversine_km

SOURCE = "municipalities"
POP_PID = "17100142"
POP_URL = f"https://www150.statcan.gc.ca/n1/tbl/csv/{POP_PID}-eng.zip"
CGNS_URL = "https://geogratis.gc.ca/services/geoname/en/geonames.json"
# A box that comfortably contains the 40 km circle (about 0.36 deg latitude, 0.55 deg longitude).
BBOX = "-123.9,48.7,-121.9,49.8"
BC_PROVINCE_CODE = "59"
BORDERLINE_KM = 3.0
POINT_PRIORITY = {
    "named_place": ("CITY", "TOWN", "VILG", "MUN1", "MUN2"),
    "area": ("MUN1", "MUN2", "CITY", "TOWN", "VILG"),
}
CGNS_CODES = ("CITY", "TOWN", "VILG", "MUN1", "MUN2")

# CSD type -> (kind, which CGNS record to prefer).
MUNICIPAL_TYPES = {
    "CY": ("municipality", "named_place"),  # city
    "T": ("municipality", "named_place"),  # town
    "VL": ("municipality", "named_place"),  # village
    "DM": ("municipality", "area"),  # district municipality
    "IM": ("municipality", "area"),  # island municipality
    "RGM": ("municipality", "area"),  # regional municipality
    "RDA": ("electoral_area", "area"),  # regional district electoral area
}

# CGNS has no usable record for these; the point and its source are stated here, not hidden.
MANUAL_POINTS = {  # code -> (latitude, longitude, point_source)
    "5915020": (
        49.2606,
        -123.2460,
        "manual: UBC campus (Electoral Area A has no CGNS record)",
    ),
}


@dataclass(frozen=True)
class Municipality:
    csd_code: str
    name: str
    csd_type: str
    kind: str
    population: int | None
    population_year: int | None
    latitude: float
    longitude: float
    point_source: str
    distance_km: float
    in_scope: bool
    borderline: bool


def fetch(raw: Path) -> list[Fetched]:
    out = [download(SOURCE, POP_URL, raw / SOURCE / f"{POP_PID}-eng.zip")]
    for code in CGNS_CODES:
        url = f"{CGNS_URL}?bbox={BBOX}&province={BC_PROVINCE_CODE}&concise={code}&num=1000"
        out.append(download(SOURCE, url, raw / SOURCE / f"cgns-{code}.json"))
    return out


_GEO = re.compile(r"^(?P<name>.+) \((?P<type>[A-Z]+)\), British Columbia$")


def parse_population(text: str) -> dict[str, tuple[str, str, int, int]]:
    """Latest population per BC census subdivision: code -> (name, type, population, year)."""
    latest: dict[str, tuple[str, str, int, int]] = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        dguid = row["DGUID"]
        m = _GEO.match(row["GEO"])
        if not m or not dguid[-7:].startswith("59") or not row["VALUE"].strip():
            continue
        code, year = dguid[-7:], int(row["REF_DATE"])
        if code not in latest or year > latest[code][3]:
            latest[code] = (m["name"], m["type"], int(float(row["VALUE"])), year)
    return latest


def parse_cgns(documents: dict[str, str]) -> dict[str, list[dict]]:
    """CGNS records by name: name -> [{'concise', 'id', 'latitude', 'longitude'}]."""
    by_name: dict[str, list[dict]] = {}
    for concise, text in documents.items():
        for item in json.loads(text)["items"]:
            by_name.setdefault(item["name"], []).append(
                {
                    "concise": concise,
                    "id": item["id"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                }
            )
    return by_name


def choose_point(records: list[dict], style: str) -> dict | None:
    """Pick the CGNS record by priority; the first listed record wins within a code."""
    for concise in POINT_PRIORITY[style]:
        for record in records:
            if record["concise"] == concise:
                return record
    return None


def build(
    population: dict[str, tuple[str, str, int, int]], cgns: dict[str, list[dict]]
) -> list[Municipality]:
    out = []
    for code, (name, csd_type, pop, year) in sorted(population.items()):
        if csd_type not in MUNICIPAL_TYPES:
            continue
        kind, style = MUNICIPAL_TYPES[csd_type]
        if code in MANUAL_POINTS:
            lat, lon, source = MANUAL_POINTS[code]
        else:
            record = choose_point(cgns.get(name, []), style)
            if record is None:
                continue  # not inside the search box, so not a candidate
            lat, lon = record["latitude"], record["longitude"]
            source = f"cgns:{record['concise']}:{record['id']}"
        distance = haversine_km(*WATERFRONT_STATION, lat, lon)
        out.append(
            Municipality(
                code,
                name,
                csd_type,
                kind,
                pop,
                year,
                lat,
                lon,
                source,
                round(distance, 2),
                distance <= SCOPE_RADIUS_KM,
                abs(distance - SCOPE_RADIUS_KM) <= BORDERLINE_KM,
            )  # fmt: skip
        )
    return out


def load(raw: Path) -> list[Municipality]:
    with zipfile.ZipFile(raw / SOURCE / f"{POP_PID}-eng.zip") as archive:
        population = parse_population(archive.read(f"{POP_PID}.csv").decode("utf-8"))
    documents = {
        code: (raw / SOURCE / f"cgns-{code}.json").read_text(encoding="utf-8")
        for code in CGNS_CODES
    }
    return build(population, parse_cgns(documents))
