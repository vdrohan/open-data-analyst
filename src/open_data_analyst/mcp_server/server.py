"""MCP server over the housing store.

Two ways in, one set of guardrails. The primitives (describe_schema, run_sql,
mortgage_payment, make_chart) let a client such as Claude Desktop do the reasoning itself, at no
API cost; every query still goes through the read-only store with its row and time limits.
`ask` runs this project's own evaluated Haiku agent, which shows its query and abstains rather
than guess; it is the only tool that spends API money, and it has a spend cap.

    uv run python -m open_data_analyst.mcp_server            # stdio, for Claude Desktop
"""

import json
from collections.abc import Callable
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from open_data_analyst.agent.loop import Agent, BudgetExceeded
from open_data_analyst.agent.sql import ReadOnlyStore, SQLRefused
from open_data_analyst.agent.tools import run_tool
from open_data_analyst.data.store import DEFAULT_DB
from open_data_analyst.mcp_server.charts import ChartError, chart_spec

DEFAULT_ASK_BUDGET_USD = 0.25  # total `ask` spend per server process

INSTRUCTIONS = (
    "Canadian housing data (Bank of Canada rates, Statistics Canada rents, CMHC new-home sales) "
    "for municipalities within 40 km of downtown Vancouver. Call describe_schema first and read "
    "the table limits. Show the SQL behind every number and decline rather than guess. "
    "`ask` runs a guarded agent and costs API money; the other tools are free."
)


def _client():
    import anthropic

    return anthropic.Anthropic()


def build_server(
    db_path: Path = DEFAULT_DB,
    client_factory: Callable[[], object] = _client,
    ask_budget_usd: float = DEFAULT_ASK_BUDGET_USD,
) -> MCPServer:
    server = MCPServer("open-data-analyst", instructions=INSTRUCTIONS)
    state: dict = {"agent": None}

    def primitive(name: str, args: dict) -> str:
        store = ReadOnlyStore(db_path)
        try:
            text, is_error = run_tool(store, name, args, set())
        finally:
            store.close()
        if is_error:
            raise ToolError(text)
        return text

    @server.tool()
    def describe_schema() -> str:
        """Every table with its description and limits, and every column. Call this first."""
        return primitive("describe_schema", {})

    @server.tool()
    def run_sql(sql: str) -> str:
        """Run one read-only DuckDB SELECT. At most 50 rows and 10 seconds; writes are refused."""
        return primitive("run_sql", {"sql": sql})

    @server.tool()
    def mortgage_payment(
        price: float,
        annual_rate_pct: float,
        down_payment_pct: float = 20,
        amortization_years: int = 25,
    ) -> str:
        """Monthly payment on a Canadian fixed-rate mortgage (semi-annual compounding).
        Excludes property tax, strata fees, insurance and CMHC premiums."""
        return primitive(
            "mortgage_payment",
            {
                "price": price,
                "annual_rate_pct": annual_rate_pct,
                "down_payment_pct": down_payment_pct,
                "amortization_years": amortization_years,
            },
        )

    @server.tool()
    def make_chart(sql: str, kind: str, x: str, y: str, title: str = "") -> str:
        """Run a read-only SELECT and return a Vega-Lite chart spec (JSON) of column `y` against
        column `x`. `kind` is "bar" or "line". The spec embeds the data and the query is echoed."""
        store = ReadOnlyStore(db_path)
        try:
            result = store.query(sql)
        except SQLRefused as exc:
            raise ToolError(str(exc)) from exc
        finally:
            store.close()
        try:
            spec = chart_spec(result.columns, result.rows, kind, x, y, title)
        except ChartError as exc:
            raise ToolError(str(exc)) from exc
        note = " (truncated to 50 rows)" if result.truncated else ""
        return json.dumps({"query": sql, "note": note.strip(), "vega_lite": spec})

    @server.tool()
    def ask(question: str) -> str:
        """Ask the guarded housing agent (Claude Haiku). It returns the answer with the SQL it
        ran, or says why it cannot answer. Costs about $0.002 per question on the API."""
        try:
            if state["agent"] is None:
                state["agent"] = Agent(client_factory(), db_path, max_cost_usd=ask_budget_usd)
            agent = state["agent"]
            answer = agent.ask(question)
        except BudgetExceeded as exc:
            return f"Declined: the ask budget for this session is used up ({exc})."
        except Exception as exc:  # no key, network, API errors: tell the client, do not crash
            return f"Declined: the agent could not run ({type(exc).__name__}: {exc})."
        log = agent.logs[-1]
        cost = f"cost ${log.cost_usd:.4f}, {log.steps} steps"
        if answer.abstained:
            reason = log.explanation or f"the agent stopped without an answer ({log.final})"
            return f"Cannot answer: {reason}\n({cost})"
        return f"Answer: {answer.value}\nQuery: {answer.query}\n{log.explanation}\n({cost})"

    return server
