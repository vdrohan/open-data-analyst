"""The agent: a Claude tool-use loop over the read-only store.

The model client is injected (anything with `messages.create`, like `anthropic.Anthropic()`),
so the loop is tested with a fake and no spend. Every question logs its tokens and cost.
"""

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from open_data_analyst.agent.sql import ReadOnlyStore
from open_data_analyst.agent.tools import TOOLS, normalise_sql, run_tool
from open_data_analyst.evals.schema import Question
from open_data_analyst.evals.scoring import AgentAnswer

DEFAULT_MODEL = "claude-haiku-5-5"
MAX_STEPS = 10
MAX_TOKENS = 4096

# USD per million tokens (input, output) for prompts under 100K tokens.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (3.00, 15.00),
    "claude-opus-5-5": (4.00, 20.00),
}

SYSTEM_PROMPT = """\
You answer questions about Canadian housing costs using a DuckDB database of public data \
(Bank of Canada, Statistics Canada, CMHC) and a mortgage calculator. The scope is \
municipalities within 40 km of Waterfront Station in Vancouver.

Rules:
1. Every number comes from run_sql or mortgage_payment, never from memory or mental arithmetic. \
Call describe_schema first and read the table descriptions: they state what each table can and \
cannot answer.
2. Answer only what the data supports. If the question needs a geography, dwelling type, \
bedroom count, period or measure the tables do not contain, or asks for a forecast, an opinion \
or advice, call abstain and say what is missing. A wrong confident number is worse than \
declining. Do not substitute a nearby measure and present it as the one asked for.
3. For a mortgage question, unless the user says otherwise: 20% down, 25 year amortization, and \
the latest posted 5-year rate in the data. State these assumptions in the explanation.
4. Finish with exactly one call to submit_answer or abstain. submit_answer's `query` must be a \
query you ran with run_sql that returned the figures behind the answer; for a mortgage answer \
that is the query for the price. Give the value in the unit the question asks for \
(CAD per month, percent, a count) as a JSON number with no thousands separators, rounded to at \
most 2 decimals. When the answer is a place, give just its name (for example "Langley"), not a \
description or code. To decline, call abstain; never submit "abstain" as a value.
"""

# Text a model might put in `value` to decline; declining must go through the abstain tool.
DECLINE_WORDS = frozenset({"abstain", "abstained", "cannot answer", "n/a", "unknown"})


@dataclass
class CallLog:
    """One question's cost and trace."""

    question_id: str
    model: str
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    queries: list[str] = field(default_factory=list)
    final: str = ""  # submit_answer, abstain, or why the loop ended without one
    explanation: str = ""

    def to_json(self) -> dict:
        return asdict(self)


class BudgetExceeded(Exception):
    pass


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, PRICES[DEFAULT_MODEL])
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


class Agent:
    def __init__(
        self,
        client,
        db_path: Path,
        model: str = DEFAULT_MODEL,
        max_steps: int = MAX_STEPS,
        max_cost_usd: float | None = None,
    ) -> None:
        self.client = client
        self.db_path = db_path
        self.model = model
        self.max_steps = max_steps
        self.max_cost_usd = max_cost_usd
        self.logs: list[CallLog] = []

    @property
    def total_cost_usd(self) -> float:
        return sum(log.cost_usd for log in self.logs)

    def __call__(self, question: Question) -> AgentAnswer:
        return self.ask(question.question, question.id)

    def ask(self, text: str, question_id: str = "") -> AgentAnswer:
        log = CallLog(question_id, self.model)
        self.logs.append(log)
        store = ReadOnlyStore(self.db_path)
        try:
            return self._loop(store, text, log)
        finally:
            store.close()

    def _loop(self, store: ReadOnlyStore, text: str, log: CallLog) -> AgentAnswer:
        messages: list[dict] = [{"role": "user", "content": text}]
        ran: set[str] = set()
        for _ in range(self.max_steps):
            if self.max_cost_usd is not None and self.total_cost_usd >= self.max_cost_usd:
                raise BudgetExceeded(f"spent ${self.total_cost_usd:.4f}, cap ${self.max_cost_usd}")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            log.steps += 1
            log.input_tokens += response.usage.input_tokens
            log.output_tokens += response.usage.output_tokens
            log.cost_usd += cost_usd(
                self.model, response.usage.input_tokens, response.usage.output_tokens
            )
            if response.stop_reason == "refusal":
                log.final = "model_refusal"
                return AgentAnswer(abstained=True)

            calls = [b for b in response.content if b.type == "tool_use"]
            if not calls:
                log.final = "no_final_answer"  # the model stopped without a final tool call
                return AgentAnswer(abstained=True)

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for call in calls:
                if call.name == "abstain":
                    log.final, log.explanation = "abstain", str(call.input.get("reason", ""))
                    return AgentAnswer(abstained=True)
                if call.name == "submit_answer":
                    error = self._check_submission(call.input, ran)
                    if error is None:
                        log.final = "submit_answer"
                        log.explanation = str(call.input.get("explanation", ""))
                        return AgentAnswer(
                            value=_clean_value(call.input["value"]), query=call.input["query"]
                        )
                    results.append(_result(call.id, error, True))
                    continue
                output, is_error = run_tool(store, call.name, call.input, ran)
                if call.name == "run_sql":
                    log.queries.append(str(call.input.get("sql", "")))
                results.append(_result(call.id, output, is_error))
            messages.append({"role": "user", "content": results})
        log.final = "step_cap"
        return AgentAnswer(abstained=True)

    @staticmethod
    def _check_submission(args: dict, ran: set[str]) -> str | None:
        if "value" not in args or "query" not in args:
            return "submit_answer needs `value` and `query`."
        value = args["value"]
        if isinstance(value, str) and value.strip().casefold() in DECLINE_WORDS:
            return "To decline, call the abstain tool; `value` must be the answer itself."
        if normalise_sql(str(args["query"])) not in ran:
            return (
                "`query` must be exactly a query you already ran successfully with run_sql. "
                "Run it first, or submit the query you ran."
            )
        return None


def _clean_value(value):
    """The tool schema allows text, so models sometimes send a number as text ('6.19').
    A string that is purely a finite number becomes a float; anything else is left alone."""
    if isinstance(value, str):
        try:
            number = float(value.strip().replace(",", ""))
        except ValueError:
            return value
        if math.isfinite(number):
            return number
    return value


def _result(tool_use_id: str, content: str, is_error: bool) -> dict:
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block
