"""MCP server and chart tests: tiny database, scripted fake model, no network, no spend."""

import asyncio
import json
from pathlib import Path

import duckdb
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from open_data_analyst.mcp_server.charts import ChartError, chart_spec, render_html
from open_data_analyst.mcp_server.server import build_server
from tests.test_agent import FakeClient, tool_use


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE rent (city VARCHAR, yr DATE, dollars DOUBLE)")
    con.execute("COMMENT ON TABLE rent IS 'Average rents by city.'")
    con.execute("INSERT INTO rent VALUES ('A','2025-04-01',2000), ('B','2026-04-01',2500)")
    con.close()
    return path


def call(server, name: str, **args):
    try:
        result = asyncio.run(server.call_tool(name, args))
    except ToolError as exc:  # a deliberate tool error: its message reaches the client
        return str(exc), True
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    return text, result.is_error


def test_server_lists_the_five_tools(db):
    tools = asyncio.run(build_server(db).list_tools())
    assert {t.name for t in tools} == {
        "describe_schema",
        "run_sql",
        "mortgage_payment",
        "make_chart",
        "ask",
    }


def test_primitives_work_and_stay_read_only(db):
    server = build_server(db)
    text, err = call(server, "describe_schema")
    assert not err and "TABLE rent: Average rents by city." in text
    text, err = call(server, "run_sql", sql="SELECT dollars FROM rent WHERE city = 'B'")
    assert not err and "2500" in text
    for bad in ["DROP TABLE rent", "INSERT INTO rent VALUES ('C','2026-01-01',1)"]:
        text, err = call(server, "run_sql", sql=bad)
        assert err and "only a single SELECT" in text  # the reason reaches the client
    text, _ = call(server, "run_sql", sql="SELECT count(*) FROM rent")
    assert "2" in text  # nothing was written


def test_mortgage_tool_matches_the_known_figure(db):
    text, err = call(
        build_server(db), "mortgage_payment", price=625000, annual_rate_pct=5, down_payment_pct=20
    )
    assert not err and "2908.02" in text


def test_chart_tool_returns_spec_and_query(db):
    sql = "SELECT city, dollars FROM rent ORDER BY city"
    text, err = call(build_server(db), "make_chart", sql=sql, kind="bar", x="city", y="dollars")
    body = json.loads(text)
    assert not err and body["query"] == sql
    spec = body["vega_lite"]
    assert spec["mark"]["type"] == "bar" and len(spec["data"]["values"]) == 2
    assert spec["encoding"]["x"]["type"] == "nominal"


def test_chart_tool_refuses_writes_and_bad_columns(db):
    server = build_server(db)
    _, err = call(server, "make_chart", sql="DROP TABLE rent", kind="bar", x="a", y="b")
    assert err
    _, err = call(server, "make_chart", sql="SELECT city FROM rent", kind="bar", x="city", y="nope")
    assert err


def test_chart_spec_dates_and_validation():
    spec = chart_spec(
        ["d", "v"], [(__import__("datetime").date(2025, 4, 1), 1.5)], "line", "d", "v"
    )
    assert spec["encoding"]["x"]["type"] == "temporal"
    assert spec["data"]["values"] == [{"d": "2025-04-01", "v": 1.5}]
    with pytest.raises(ChartError, match="kind"):
        chart_spec(["a", "b"], [("x", 1)], "pie", "a", "b")
    with pytest.raises(ChartError, match="no rows"):
        chart_spec(["a", "b"], [], "bar", "a", "b")
    with pytest.raises(ChartError, match="numeric"):
        chart_spec(["a", "b"], [("x", "oops")], "bar", "a", "b")
    with pytest.raises(ChartError, match="numeric"):
        chart_spec(["a", "b"], [("x", None)], "bar", "a", "b")
    with pytest.raises(ChartError, match="too many"):
        chart_spec(["a", "b"], [("x", 1)] * 51, "bar", "a", "b")
    assert "vegaEmbed" in render_html(spec)


def test_ask_returns_answer_with_query_and_cost(db):
    sql = "SELECT dollars FROM rent WHERE city = 'B'"
    client = FakeClient(
        [tool_use("run_sql", {"sql": sql})],
        [tool_use("submit_answer", {"value": 2500, "query": sql, "explanation": "B rent."})],
    )
    text, err = call(build_server(db, lambda: client), "ask", question="Rent in B?")
    assert not err and "Answer: 2500.0" in text or "Answer: 2500" in text
    assert sql in text and "cost $" in text


def test_ask_abstains_and_reports_failures_without_crashing(db):
    client = FakeClient([tool_use("abstain", {"reason": "No such data."})])
    text, _ = call(build_server(db, lambda: client), "ask", question="Rent on Mars?")
    assert text.startswith("Cannot answer: No such data.")

    def no_key():
        raise RuntimeError("no API key")

    text, err = call(build_server(db, no_key), "ask", question="Anything?")
    assert not err and text.startswith("Declined: the agent could not run")


def test_ask_stops_at_its_budget(db):
    sql = "SELECT 1"
    answer = (
        [tool_use("run_sql", {"sql": sql})],
        [tool_use("submit_answer", {"value": 1, "query": sql, "explanation": "one"})],
    )
    client = FakeClient(*answer, *answer)
    server = build_server(db, lambda: client, ask_budget_usd=0.0003)
    first, _ = call(server, "ask", question="one?")
    assert first.startswith("Answer")
    second, _ = call(server, "ask", question="again?")
    assert second.startswith("Declined: the ask budget")
