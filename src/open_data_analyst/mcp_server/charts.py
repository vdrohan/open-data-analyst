"""Turn a query result into a Vega-Lite chart spec.

The spec is plain JSON with the data embedded, so any Vega-Lite renderer (Claude Desktop, a
web page, the Phase 5 UI) can draw it and nothing is stored on disk.
"""

import datetime
import decimal
import json

KINDS = ("bar", "line")
SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"
MAX_POINTS = 50  # matches the SQL row cap, so a chart never silently drops rows


class ChartError(ValueError):
    """The result cannot be drawn as asked. The message is safe to show the model."""


def _jsonable(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


def _is_number(value) -> bool:
    return isinstance(value, (int, float, decimal.Decimal)) and not isinstance(value, bool)


def _x_type(values: list, kind: str) -> str:
    sample = next((v for v in values if v is not None), None)
    if isinstance(sample, (datetime.date, datetime.datetime)):
        return "temporal"
    if _is_number(sample):
        return "quantitative" if kind == "line" else "ordinal"
    return "nominal"


def chart_spec(
    columns: list[str], rows: list[tuple], kind: str, x: str, y: str, title: str = ""
) -> dict:
    """A Vega-Lite spec drawing column `y` against column `x` from the given rows."""
    if kind not in KINDS:
        raise ChartError(f"kind must be one of {', '.join(KINDS)}, not {kind!r}")
    for name in (x, y):
        if name not in columns:
            raise ChartError(f"column {name!r} is not in the result; columns are {columns}")
    if not rows:
        raise ChartError("the query returned no rows, so there is nothing to draw")
    if len(rows) > MAX_POINTS:
        raise ChartError(f"too many rows to chart ({len(rows)}); aggregate or filter first")
    xi, yi = columns.index(x), columns.index(y)
    ys = [row[yi] for row in rows]
    if not all(_is_number(v) for v in ys):
        raise ChartError(f"column {y!r} must be numeric and have no missing values to be charted")
    mark = {"type": "line", "point": True} if kind == "line" else {"type": "bar"}
    return {
        "$schema": SCHEMA,
        "title": title or f"{y} by {x}",
        "data": {
            "values": [{c: _jsonable(v) for c, v in zip(columns, row, strict=True)} for row in rows]
        },
        "mark": mark,
        "encoding": {
            "x": {"field": x, "type": _x_type([row[xi] for row in rows], kind), "sort": None},
            "y": {"field": y, "type": "quantitative"},
            "tooltip": [{"field": x}, {"field": y}],
        },
        "width": 560,
        "height": 320,
    }


def render_html(spec: dict) -> str:
    """A single self-contained page that draws the spec (loads the renderer from a CDN)."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{spec.get("title", "chart")}</title>
<script src="https://cdn.jsdelivr.net/npm/vega@5.30.0"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5.21.0"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6.26.0"></script></head>
<body><div id="chart"></div>
<script>vegaEmbed("#chart", {json.dumps(spec)});</script></body></html>
"""
