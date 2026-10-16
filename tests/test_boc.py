from datetime import date

import pytest

from open_data_analyst.data.boc import parse_valet_csv

VALET = """﻿"TERMS AND CONDITIONS"
"https://www.bankofcanada.ca/terms/"

"SERIES"
"id","label","description","date_format"
"V80691335","Conventional mortgage, 5-year","...","weekly"

"OBSERVATIONS"
"date","V80691335"
"2026-10-07","6.19"
"2026-10-14","6.19"
"2026-10-21",""
"""


def test_parses_observations_and_skips_blank_values():
    rows = parse_valet_csv(VALET, "V80691335")
    assert [(r.observation_date, r.rate_pct) for r in rows] == [
        (date(2026, 10, 7), 6.19),
        (date(2026, 10, 14), 6.19),
    ]
    assert rows[0].frequency == "weekly"


def test_wrong_series_header_is_an_error():
    with pytest.raises(ValueError, match="unexpected Valet header"):
        parse_valet_csv(VALET, "V122521")
