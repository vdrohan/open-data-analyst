"""Eval question format.

Each question has one exact, checkable answer, or is unanswerable from the data and
must be refused. Numeric questions carry the SQL (and, for mortgage questions, the
payment inputs) that produced the expected value, so `verify` can re-derive every
expected number after a data refresh instead of trusting a stored constant.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

ANSWER_TYPES = ("number", "text", "bool", "abstain")
CATEGORIES = ("lookup", "calc", "scope", "abstain")
DEFAULT_PATH = Path("data/eval/questions.jsonl")


@dataclass(frozen=True)
class MortgageStep:
    """Turn the first value returned by the reference SQL (a price) into a monthly payment."""

    rate_pct: float
    down_payment_pct: float = 0.20
    amortization_years: int = 25


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    question: str
    answer_type: str
    expected: float | str | bool | None  # None only for abstain questions
    unit: str = ""
    abs_tol: float = 0.0  # numbers: accepted absolute error
    rel_tol: float = 0.0  # numbers: accepted relative error; the looser of the two applies
    reference_sql: str = ""  # returns one row, one column
    mortgage: MortgageStep | None = None
    # optional: subtract this query's value from the payment (e.g. a rent). For a bool
    # question the expected answer is whether the result is above zero.
    minus_sql: str = ""
    volatile: bool = False  # expected value changes when new data arrives; drift is a warning
    why_abstain: str = ""  # abstain questions: what the data cannot support
    notes: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"{self.id}: unknown category {self.category!r}")
        if self.answer_type not in ANSWER_TYPES:
            raise ValueError(f"{self.id}: unknown answer_type {self.answer_type!r}")
        if (self.answer_type == "abstain") != (self.expected is None):
            raise ValueError(f"{self.id}: expected is None exactly when the answer is a refusal")
        if self.answer_type == "abstain" and not self.why_abstain:
            raise ValueError(f"{self.id}: abstain questions must say what the data cannot support")
        if self.answer_type != "abstain" and not self.reference_sql:
            raise ValueError(f"{self.id}: answerable questions need reference_sql")


def load_questions(path: Path = DEFAULT_PATH) -> list[Question]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("mortgage"):
            row["mortgage"] = MortgageStep(**row["mortgage"])
        questions.append(Question(**row))
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question ids")
    return questions
