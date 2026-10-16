"""Score one agent answer against one question."""

from dataclasses import dataclass

from open_data_analyst.evals.schema import Question


@dataclass(frozen=True)
class AgentAnswer:
    """What the agent hands back. `query` is the SQL it ran (rule: every answer shows its query)."""

    value: float | str | bool | None = None
    abstained: bool = False
    query: str = ""


# Outcomes, from best to worst. "overreach" and "wrong" are the confident-wrong failures.
CORRECT = "correct"
CORRECT_REFUSAL = "correct_refusal"
MISSED = "missed"  # refused a question the data can answer
WRONG = "wrong"  # answered an answerable question with the wrong value
OVERREACH = "overreach"  # answered a question the data cannot support
NO_QUERY = "no_query"  # right value but no query shown


@dataclass(frozen=True)
class Score:
    outcome: str
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.outcome in (CORRECT, CORRECT_REFUSAL)


def _number_ok(question: Question, value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    expected = float(question.expected)  # type: ignore[arg-type]
    allowed = max(question.abs_tol, question.rel_tol * abs(expected))
    return abs(float(value) - expected) <= allowed + 1e-9


def score(question: Question, answer: AgentAnswer) -> Score:
    if question.answer_type == "abstain":
        if answer.abstained:
            return Score(CORRECT_REFUSAL)
        return Score(
            OVERREACH, f"answered {answer.value!r}; data cannot support: {question.why_abstain}"
        )
    if answer.abstained:
        return Score(MISSED, "refused an answerable question")
    if question.answer_type == "number":
        ok = _number_ok(question, answer.value)
    elif question.answer_type == "bool":
        ok = isinstance(answer.value, bool) and answer.value == question.expected
    else:
        ok = (
            isinstance(answer.value, str)
            and answer.value.strip().casefold() == str(question.expected).strip().casefold()
        )
    if not ok:
        return Score(WRONG, f"got {answer.value!r}, expected {question.expected!r}")
    if not answer.query.strip():
        return Score(NO_QUERY, "correct value but no query shown")
    return Score(CORRECT)
