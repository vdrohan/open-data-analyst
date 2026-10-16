"""Agent tests run against a tiny database and a scripted fake model: no network, no spend."""

from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from open_data_analyst.agent.loop import Agent, BudgetExceeded, cost_usd
from open_data_analyst.agent.sql import ReadOnlyStore, SQLRefused
from open_data_analyst.agent.tools import TOOLS
from open_data_analyst.evals.runner import run
from open_data_analyst.evals.schema import Question


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE rent (city VARCHAR, dollars DOUBLE)")
    con.execute("COMMENT ON TABLE rent IS 'Average rents by city.'")
    con.execute("COMMENT ON COLUMN rent.dollars IS 'Dollars per month.'")
    con.execute("INSERT INTO rent VALUES ('A', 2000), ('B', 2500)")
    con.close()
    return path


def tool_use(name: str, input: dict, id: str = "t1"):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


class FakeClient:
    """Replays scripted responses and records the requests it received."""

    def __init__(self, *turns: list, stop_reason: str = "tool_use") -> None:
        self.turns = list(turns)
        self.requests: list[dict] = []
        self.stop_reason = stop_reason
        self.messages = self

    def create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        blocks = self.turns.pop(0)
        usage = SimpleNamespace(input_tokens=1000, output_tokens=100)
        return SimpleNamespace(content=blocks, stop_reason=self.stop_reason, usage=usage)


def test_store_refuses_writes_and_other_statements(db):
    store = ReadOnlyStore(db)
    for sql in [
        "DROP TABLE rent",
        "INSERT INTO rent VALUES ('C', 1)",
        "SELECT 1; SELECT 2",
        "ATTACH 'x.duckdb'",
        "COPY (SELECT 1) TO 'x.csv'",
        "SET enable_external_access = true",
        "",
    ]:
        with pytest.raises(SQLRefused):
            store.query(sql)
    assert store.query("SELECT count(*) FROM rent").rows == [(2,)]


def test_store_blocks_file_access(db):
    with pytest.raises(SQLRefused):
        ReadOnlyStore(db).query("SELECT * FROM read_csv('/etc/passwd')")


def test_store_connection_is_read_only(db):
    with pytest.raises(duckdb.Error):
        ReadOnlyStore(db)._con.execute("CREATE TABLE x (a INT)")


def test_store_row_limit_and_timeout(db):
    store = ReadOnlyStore(db, max_rows=5, timeout=0.5)
    result = store.query("SELECT * FROM range(100)")
    assert len(result.rows) == 5 and result.truncated
    assert "more" in result.as_text()
    with pytest.raises(SQLRefused, match="stopped after"):
        store.query("SELECT count(*) FROM range(10000000000)")


def test_schema_text_includes_comments(db):
    text = ReadOnlyStore(db).schema_text()
    assert "TABLE rent: Average rents by city." in text
    assert "dollars DOUBLE: Dollars per month." in text


def test_answer_with_sql_then_submit(db):
    sql = "SELECT dollars FROM rent WHERE city = 'B'"
    client = FakeClient(
        [tool_use("describe_schema", {})],
        [tool_use("run_sql", {"sql": sql})],
        [tool_use("submit_answer", {"value": 2500, "query": sql + ";", "explanation": "B"})],
    )
    agent = Agent(client, db)
    answer = agent.ask("What is the rent in B?", "q1")
    assert answer.value == 2500 and answer.query.startswith("SELECT") and not answer.abstained
    log = agent.logs[0]
    assert log.steps == 3 and log.final == "submit_answer" and log.queries == [sql]
    assert log.input_tokens == 3000 and log.cost_usd == pytest.approx(
        cost_usd(agent.model, 3000, 300)
    )
    assert client.requests[0]["model"] == "claude-haiku-5-5"
    # the second request carries the schema result back to the model
    last = client.requests[1]["messages"][-1]["content"][0]
    assert last["type"] == "tool_result" and "Average rents" in last["content"]


def test_submit_with_unrun_query_is_bounced_then_accepted(db):
    sql = "SELECT dollars FROM rent WHERE city = 'A'"
    client = FakeClient(
        [tool_use("submit_answer", {"value": 2000, "query": sql, "explanation": "A"})],
        [tool_use("run_sql", {"sql": sql})],
        [tool_use("submit_answer", {"value": 2000, "query": sql, "explanation": "A"})],
    )
    answer = Agent(client, db).ask("rent in A?")
    assert answer.value == 2000
    bounce = client.requests[1]["messages"][-1]["content"][0]
    assert bounce["is_error"] and "already ran" in bounce["content"]


def test_mortgage_tool_matches_calculator(db):
    from open_data_analyst.finance import mortgage_payment

    client = FakeClient(
        [tool_use("mortgage_payment", {"price": 800000, "annual_rate_pct": 6.19})],
        [tool_use("abstain", {"reason": "done"})],
    )
    Agent(client, db).ask("payment?")
    result = client.requests[1]["messages"][-1]["content"][0]["content"]
    assert result == f"{mortgage_payment(800000, 0.0619):.2f} CAD per month"


def test_abstain_and_failure_modes_all_abstain(db):
    agent = Agent(FakeClient([tool_use("abstain", {"reason": "no data"})]), db)
    assert agent.ask("q").abstained and agent.logs[0].explanation == "no data"
    # model stops without a final tool call
    agent = Agent(FakeClient([SimpleNamespace(type="text", text="hmm")]), db)
    assert agent.ask("q").abstained and agent.logs[0].final == "no_final_answer"
    # never finishes: step cap
    turns = [[tool_use("describe_schema", {})] for _ in range(3)]
    agent = Agent(FakeClient(*turns), db, max_steps=3)
    assert agent.ask("q").abstained and agent.logs[0].final == "step_cap"
    # safety refusal
    agent = Agent(FakeClient([], stop_reason="refusal"), db)
    assert agent.ask("q").abstained and agent.logs[0].final == "model_refusal"


def test_bad_sql_goes_back_to_the_model_as_an_error(db):
    client = FakeClient(
        [tool_use("run_sql", {"sql": "DROP TABLE rent"})],
        [tool_use("abstain", {"reason": "x"})],
    )
    Agent(client, db).ask("q")
    result = client.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] and "only a single SELECT" in result["content"]


def test_budget_cap_stops_before_the_next_call(db):
    turns = [[tool_use("describe_schema", {})] for _ in range(5)]
    agent = Agent(FakeClient(*turns), db, max_steps=5, max_cost_usd=0.0001)
    with pytest.raises(BudgetExceeded):
        agent.ask("q")


def test_agent_plugs_into_the_eval_runner(db):
    sql = "SELECT dollars FROM rent WHERE city = 'B'"
    questions = [
        Question("a", "lookup", "Rent in B?", "number", 2500.0, reference_sql=sql),
        Question("b", "abstain", "Rent in 2030?", "abstain", None, why_abstain="forecast"),
    ]
    client = FakeClient(
        [tool_use("run_sql", {"sql": sql})],
        [tool_use("submit_answer", {"value": 2500, "query": sql, "explanation": "B"})],
        [tool_use("abstain", {"reason": "forecast"})],
    )
    report = run(questions, Agent(client, db))
    assert report.accuracy == 1.0 and report.confident_wrong == 0


def test_tool_names_are_unique_and_final_tools_exist():
    names = [t["name"] for t in TOOLS]
    assert len(names) == len(set(names))
    assert {"submit_answer", "abstain", "run_sql", "describe_schema", "mortgage_payment"} <= set(
        names
    )
