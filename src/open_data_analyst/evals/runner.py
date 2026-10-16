"""Run an agent over the eval set, and re-derive the expected answers from the data."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb

from open_data_analyst.evals.schema import Question
from open_data_analyst.evals.scoring import (
    CORRECT,
    CORRECT_REFUSAL,
    MISSED,
    NO_QUERY,
    OVERREACH,
    WRONG,
    AgentAnswer,
    Score,
    score,
)
from open_data_analyst.finance import mortgage_payment

Agent = Callable[[Question], AgentAnswer]
OUTCOMES = (CORRECT, CORRECT_REFUSAL, MISSED, WRONG, OVERREACH, NO_QUERY)


def always_abstain(question: Question) -> AgentAnswer:
    """The floor every real agent has to beat."""
    return AgentAnswer(abstained=True)


@dataclass(frozen=True)
class Report:
    results: dict[str, Score]
    questions: list[Question]

    @property
    def counts(self) -> Counter:
        return Counter(s.outcome for s in self.results.values())

    @property
    def accuracy(self) -> float:
        return sum(s.passed for s in self.results.values()) / len(self.results)

    @property
    def confident_wrong(self) -> int:
        """Answers given with a wrong value or to an unanswerable question: the worst failure."""
        return self.counts[WRONG] + self.counts[OVERREACH]

    def summary(self) -> str:
        lines = [f"{len(self.results)} questions, accuracy {self.accuracy:.0%}"]
        lines += [f"  {o}: {self.counts[o]}" for o in OUTCOMES if self.counts[o]]
        lines.append(f"  confident-wrong (wrong + overreach): {self.confident_wrong}")
        by_cat: dict[str, list[bool]] = {}
        for q in self.questions:
            by_cat.setdefault(q.category, []).append(self.results[q.id].passed)
        lines += [f"  {c}: {sum(v)}/{len(v)}" for c, v in sorted(by_cat.items())]
        return "\n".join(lines)


def run(questions: list[Question], agent: Agent) -> Report:
    return Report({q.id: score(q, agent(q)) for q in questions}, questions)


def derive_expected(con: duckdb.DuckDBPyConnection, question: Question) -> float | str | bool:
    """Recompute a question's expected value from its reference SQL (and mortgage step)."""
    row = con.execute(question.reference_sql).fetchone()
    if row is None or row[0] is None:
        raise ValueError(f"{question.id}: reference_sql returned no value")
    value = row[0]
    if question.mortgage:
        m = question.mortgage
        payment = mortgage_payment(
            float(value), m.rate_pct / 100, m.down_payment_pct, m.amortization_years
        )
        if question.minus_sql:
            payment -= float(con.execute(question.minus_sql).fetchone()[0])
        return round(payment, 2)
    if question.answer_type == "number":
        return float(value)
    if question.answer_type == "bool":
        return bool(value)
    return str(value)


def verify(db_path: Path, questions: list[Question]) -> list[str]:
    """Problems found re-deriving expected answers. Volatile drift is reported with a ~ prefix."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        problems = []
        for q in questions:
            if q.answer_type == "abstain":
                continue
            got = derive_expected(con, q)
            probe = score(q, AgentAnswer(value=got, query="reference"))
            if not probe.passed:
                prefix = "~" if q.volatile else ""
                problems.append(f"{prefix}{q.id}: data now gives {got!r}, expected {q.expected!r}")
        return problems
    finally:
        con.close()
