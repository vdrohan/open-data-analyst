"""Bank of Canada Valet API: posted 5-year conventional mortgage rate.

V122521 is the monthly series the Phase 1 survey named, but the Bank stopped
updating it in September 2019. V80691335 is the weekly series that carries on
from it. Both are loaded and labelled so an answer never silently uses a stale
rate.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from open_data_analyst.data.http import Fetched, download

SOURCE = "boc"
VALET_CSV = "https://www.bankofcanada.ca/valet/observations/{series}/csv"
SERIES = {
    "V122521": "monthly",  # legacy, last observation 2019-09-01
    "V80691335": "weekly",  # current
}


@dataclass(frozen=True)
class RateObservation:
    series_id: str
    frequency: str
    observation_date: date
    rate_pct: float


def fetch(raw: Path) -> list[Fetched]:
    return [download(SOURCE, VALET_CSV.format(series=s), raw / SOURCE / f"{s}.csv") for s in SERIES]


def parse_valet_csv(text: str, series_id: str) -> list[RateObservation]:
    """Parse a Valet CSV download: metadata blocks first, then an OBSERVATIONS block."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    start = next(i for i, row in enumerate(rows) if row and row[0] == "OBSERVATIONS")
    header = rows[start + 1]
    if header != ["date", series_id]:
        raise ValueError(f"unexpected Valet header {header!r} for {series_id}")
    frequency = SERIES[series_id]
    out = []
    for row in rows[start + 2 :]:
        if len(row) < 2 or not row[1].strip():
            continue
        out.append(RateObservation(series_id, frequency, date.fromisoformat(row[0]), float(row[1])))
    return out


def load(raw: Path) -> list[RateObservation]:
    out: list[RateObservation] = []
    for series in SERIES:
        text = (raw / SOURCE / f"{series}.csv").read_text(encoding="utf-8")
        out.extend(parse_valet_csv(text, series))
    return out
