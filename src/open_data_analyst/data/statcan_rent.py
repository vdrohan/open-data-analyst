"""Statistics Canada table 46-10-0092-01: asking and paid rent (experimental, quarterly, CMA)."""

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from open_data_analyst.data.http import Fetched, download

SOURCE = "statcan_rent"
PID = "46100092"
URL = f"https://www150.statcan.gc.ca/n1/tbl/csv/{PID}-eng.zip"
# StatCan flags: E = use with caution, F = too unreliable to publish, .. = not available.
UNAVAILABLE_FLAGS = {"..", "F"}


@dataclass(frozen=True)
class RentObservation:
    ref_date: date
    geo: str
    dguid: str
    rental_unit_type: str
    estimate: str
    rent_dollars: int | None
    status: str
    vector: str


def fetch(raw: Path) -> list[Fetched]:
    return [download(SOURCE, URL, raw / SOURCE / f"{PID}-eng.zip")]


def parse_csv(text: str) -> list[RentObservation]:
    out = []
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        status = row["STATUS"].strip()
        value = row["VALUE"].strip()
        unavailable = status in UNAVAILABLE_FLAGS or not value
        year, month = row["REF_DATE"].split("-")
        out.append(
            RentObservation(
                ref_date=date(int(year), int(month), 1),
                geo=row["GEO"],
                dguid=row["DGUID"],
                rental_unit_type=row["Rental unit type"],
                estimate=row["Estimates"],
                rent_dollars=None if unavailable else int(float(value)),
                status=status,
                vector=row["VECTOR"],
            )
        )
    return out


def load(raw: Path) -> list[RentObservation]:
    with zipfile.ZipFile(raw / SOURCE / f"{PID}-eng.zip") as archive:
        return parse_csv(archive.read(f"{PID}.csv").decode("utf-8"))
