"""Tool definitions the model sees, and the code that runs them."""

from open_data_analyst.agent.sql import ReadOnlyStore, SQLRefused
from open_data_analyst.finance import mortgage_payment

TOOLS: list[dict] = [
    {
        "name": "describe_schema",
        "description": (
            "List every table in the housing database with a description of what it holds and "
            "its limits, and every column with its type and meaning. Call this before writing SQL."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_sql",
        "description": (
            "Run one read-only DuckDB SELECT (or WITH ... SELECT) query. Returns at most 50 rows "
            "and stops after 10 seconds. Writes, several statements and file access are refused."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "A single SELECT statement."}},
            "required": ["sql"],
        },
    },
    {
        "name": "mortgage_payment",
        "description": (
            "Monthly payment on a fixed-rate Canadian mortgage (semi-annual compounding). "
            "Excludes property tax, strata fees, home insurance and CMHC premiums. Do this "
            "arithmetic with this tool, never by hand."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Purchase price in CAD."},
                "annual_rate_pct": {
                    "type": "number",
                    "description": "Quoted annual rate in percent, e.g. 6.19 for 6.19%.",
                },
                "down_payment_pct": {
                    "type": "number",
                    "description": "Down payment in percent of the price. Default 20.",
                },
                "amortization_years": {"type": "integer", "description": "Default 25."},
            },
            "required": ["price", "annual_rate_pct"],
        },
    },
    {
        "name": "submit_answer",
        "description": (
            "Give the final answer. `value` is the single number, text or true/false that answers "
            "the question. `query` must be the exact SQL, passed to run_sql earlier, that produced "
            "the figures behind the answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "value": {
                    "anyOf": [{"type": "number"}, {"type": "string"}, {"type": "boolean"}],
                    "description": "The answer: a number, a short text, or true/false.",
                },
                "query": {"type": "string", "description": "The SQL behind the answer."},
                "explanation": {
                    "type": "string",
                    "description": "One or two sentences: what the number is, the unit, and any "
                    "assumptions or limits the reader should know.",
                },
            },
            "required": ["value", "query", "explanation"],
        },
    },
    {
        "name": "abstain",
        "description": (
            "Decline to answer because the data cannot support the question, or the answer would "
            "be a guess. Say what is missing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]

FINAL_TOOLS = ("submit_answer", "abstain")


def normalise_sql(sql: str) -> str:
    return " ".join(sql.strip().rstrip(";").split())


def run_tool(store: ReadOnlyStore, name: str, args: dict, ran: set[str]) -> tuple[str, bool]:
    """Execute a non-final tool. Returns (text for the model, is_error). Successful SQL is
    remembered in `ran` so submit_answer can check the cited query was really executed."""
    try:
        if name == "describe_schema":
            return store.schema_text(), False
        if name == "run_sql":
            result = store.query(args["sql"])
            ran.add(normalise_sql(args["sql"]))
            return result.as_text(), False
        if name == "mortgage_payment":
            payment = mortgage_payment(
                float(args["price"]),
                float(args["annual_rate_pct"]) / 100,
                float(args.get("down_payment_pct", 20)) / 100,
                int(args.get("amortization_years", 25)),
            )
            return f"{payment:.2f} CAD per month", False
        return f"unknown tool {name!r}", True
    except SQLRefused as exc:
        return str(exc), True
    except (KeyError, TypeError, ValueError) as exc:
        return f"bad tool input: {exc}", True
