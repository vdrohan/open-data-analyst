"""CMHC "Absorbed Units by Price Range": newly built homes sold, by price band.

One Excel workbook per period and geography, one sheet per CMA, one block of
rows per census subdivision (municipality) and dwelling type. Price bands
differ from file to file, so the loader keeps each band's bounds as numbers.
Only the CMA workbooks are loaded; CMHC's agglomeration (CA) workbooks stop at 2022 and
cover centres far from Vancouver.

Periods: CMHC publishes every month, quarter and full year. Loading all three
would count each home up to three times, so this loader takes full years while
they exist and months only for years that have no annual edition yet.
"""

import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import openpyxl

from open_data_analyst.data.http import Fetched, download, get_bytes

SOURCE = "cmhc_absorbed"
SITE = "https://www.cmhc-schl.gc.ca"
DATA_SOURCE_ITEM = (
    "/sitecore/content/CMHC/Sites/Main/Home/professionals/housing-markets-data-and-research/"
    "housing-data/data-tables/housing-market-data/absorbed-units-price-range"
)
CMA_GEOGRAPHY_ID = "{92FA01A9-50EA-4558-B4C7-A3867FA3543F}"
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip
CMA_NAME_FIXES = {
    "Namaimo": "Nanaimo",
    "St. Catherines-Niagara": "St. Catharines-Niagara",
}  # CMHC typos
DWELLING_TYPES = {
    "Absorbed - Single": "single",
    "Absorbed - Semi-Detached": "semi",
    "Absorbed - Row": "row",
    "Absorbed - Apartment and other": "apartment",
    "Total": "total",
}


@dataclass(frozen=True)
class Edition:
    label: str
    item_id: str
    period_type: str  # "year" or "month"
    period_start: date

    @property
    def file_stem(self) -> str:
        if self.period_type == "year":
            return f"cma-{self.period_start.year}"
        return f"cma-{self.period_start:%Y-%m}"


@dataclass(frozen=True)
class PriceBand:
    """One price column. `low`/`high` are dollars; high is None for an open-ended top band."""

    label: str
    low: int
    high: int | None


@dataclass(frozen=True)
class BandCount:
    period_start: date
    period_type: str
    cma: str
    csd_code: str | None
    csd_name: str
    csd_type: str | None
    dwelling_type: str
    band_label: str
    price_low: int
    price_high: int | None
    units: int | None  # None when CMHC suppressed the cell
    suppressed: bool


@dataclass(frozen=True)
class UnitTotals:
    period_start: date
    period_type: str
    cma: str
    csd_code: str | None
    csd_name: str
    csd_type: str | None
    dwelling_type: str
    priced: int | None
    unpriced: int | None
    total: int | None


def select_editions(editions: list[dict]) -> list[Edition]:
    """Pick full-year editions, plus single months of years without a full-year edition."""
    years: dict[int, Edition] = {}
    months: list[Edition] = []
    for item in editions:
        label = item["Editions"].strip()
        if m := re.fullmatch(r"January\s*[–-]\s*December (\d{4})", label):
            year = int(m.group(1))
            years[year] = Edition(label, item["Itemid"], "year", date(year, 1, 1))
        elif m := re.fullmatch(r"([A-Z][a-z]+) (\d{4})", label):
            if m.group(1) in MONTHS:
                start = date(int(m.group(2)), MONTHS.index(m.group(1)) + 1, 1)
                months.append(Edition(label, item["Itemid"], "month", start))
    chosen = list(years.values()) + [e for e in months if e.period_start.year not in years]
    return sorted(chosen, key=lambda e: e.period_start)


def list_editions() -> list[Edition]:
    body = get_bytes(
        f"{SITE}/api/Sitecore/PubsAndReports/GetEditionList",
        {"cityId": CMA_GEOGRAPHY_ID, "dataSource": DATA_SOURCE_ITEM, "contextLanguage": "en"},
    )
    return select_editions(json.loads(body))


def file_url(edition: Edition) -> str:
    body = get_bytes(
        f"{SITE}/api/Sitecore/PubsAndReports/GetFileDetails",
        {
            "cityId": CMA_GEOGRAPHY_ID,
            "edition": "{" + edition.item_id.upper() + "}",
            "dataSource": DATA_SOURCE_ITEM,
            "contextLanguage": "en",
        },
    )
    url = json.loads(body)["DocumentUrl"]
    if urllib.parse.urlparse(url).hostname != "assets.cmhc-schl.gc.ca":
        raise ValueError(f"unexpected CMHC download host in {url}")
    return url


def fetch(raw: Path) -> list[Fetched]:
    out = []
    for edition in list_editions():
        dest = raw / SOURCE / f"{edition.file_stem}.xlsx"
        out.append(download(SOURCE, file_url(edition), dest))
    return out


_BAND = re.compile(r"^(?:<)?([\d,]+)(?:-([\d,]+)|\+)?$")


def parse_band(label: str) -> PriceBand:
    """'<299,999' -> 0..299,999; '300,000-349,999' -> 300,000..349,999; '4,000,000+' -> open."""
    text = str(label).strip()
    m = _BAND.match(text)
    if not m:
        raise ValueError(f"unrecognised price band {label!r}")
    first = int(m.group(1).replace(",", ""))
    if text.startswith("<"):
        return PriceBand(text, 0, first)
    if m.group(2):
        return PriceBand(text, first, int(m.group(2).replace(",", "")))
    return PriceBand(text, first, None)


def _count(value: object) -> tuple[int | None, bool]:
    """Return (units, suppressed). '**' is CMHC's suppression marker; blank means no figure."""
    if isinstance(value, bool):
        raise ValueError(f"unexpected boolean cell {value!r}")
    if isinstance(value, (int, float)):
        return int(value), False
    text = str(value).strip() if value is not None else ""
    if text == "**":
        return None, True
    if text == "":
        return None, False
    return int(text.replace(",", "")), False


_CSD = re.compile(r"^\((\d{7})\)\s+(.*?)(?:\s+([A-Z]{1,4}))?$")


def split_csd(cell: str) -> tuple[str | None, str, str | None]:
    """'(5915004) Surrey CY' -> ('5915004', 'Surrey', 'CY'); a CMA total row has no code."""
    m = _CSD.match(cell.strip())
    if not m:
        return None, cell.strip(), None
    return m.group(1), m.group(2).strip(), m.group(3)


def parse_sheet(
    rows: list[tuple], period_start: date, period_type: str
) -> tuple[list[BandCount], list[UnitTotals]]:
    """Parse one CMA sheet into band counts and per-row totals."""
    cma = str(rows[1][0])
    for suffix in (" Census Metropolitan Area (CMA)", " Census Agglomerations (CA)"):
        cma = cma.removesuffix(suffix)
    cma = CMA_NAME_FIXES.get(cma.strip(), cma.strip())
    header_at = next(i for i, r in enumerate(rows) if r and r[0] == "Census Subdivision")
    header = rows[header_at]
    summary_at = {str(h).strip(): i for i, h in enumerate(header) if str(h).strip() in
                  ("Priced", "Unpriced", "Total")}  # fmt: skip
    band_cols = [
        (i, parse_band(h))
        for i, h in enumerate(header)
        if i >= 2 and h is not None and str(h).strip() not in summary_at and str(h).strip()
    ]
    counts: list[BandCount] = []
    totals: list[UnitTotals] = []
    for row in rows[header_at + 1 :]:
        name_cell, dwelling_raw = row[0], row[1] if len(row) > 1 else None
        if name_cell is None or dwelling_raw is None:
            if name_cell and str(name_cell).startswith("Note"):
                break
            if name_cell and "Total" in str(name_cell):
                dwelling_raw = "Total"
            else:
                continue
        dwelling = DWELLING_TYPES.get(str(dwelling_raw).strip())
        if dwelling is None:
            continue
        code, name, csd_type = split_csd(str(name_cell))
        for col, band in band_cols:
            units, suppressed = _count(row[col] if col < len(row) else None)
            if units is None and not suppressed:
                continue
            counts.append(
                BandCount(
                    period_start,
                    period_type,
                    cma,
                    code,
                    name,
                    csd_type,
                    dwelling,
                    band.label,
                    band.low,
                    band.high,
                    units,
                    suppressed,
                )  # fmt: skip
            )
        priced, unpriced, total = (
            _count(row[summary_at[k]] if k in summary_at and summary_at[k] < len(row) else None)[0]
            for k in ("Priced", "Unpriced", "Total")
        )
        totals.append(
            UnitTotals(
                period_start,
                period_type,
                cma,
                code,
                name,
                csd_type,
                dwelling,
                priced,
                unpriced,
                total,
            )  # fmt: skip
        )
    return counts, totals


def parse_workbook(
    path: Path, period_start: date, period_type: str
) -> tuple[list[BandCount], list[UnitTotals]]:
    counts: list[BandCount] = []
    totals: list[UnitTotals] = []
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            c, t = parse_sheet(list(sheet.iter_rows(values_only=True)), period_start, period_type)
            counts.extend(c)
            totals.extend(t)
    finally:
        workbook.close()
    return counts, totals


def load(raw: Path) -> tuple[list[BandCount], list[UnitTotals]]:
    counts: list[BandCount] = []
    totals: list[UnitTotals] = []
    for path in sorted((raw / SOURCE).glob("cma-*.xlsx")):
        stem = path.stem.removeprefix("cma-")
        if len(stem) == 4:
            start, kind = date(int(stem), 1, 1), "year"
        else:
            start, kind = date(int(stem[:4]), int(stem[5:7]), 1), "month"
        c, t = parse_workbook(path, start, kind)
        counts.extend(c)
        totals.extend(t)
    return counts, totals
