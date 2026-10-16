import json
from pathlib import Path

import duckdb
import pytest

from open_data_analyst.evals.runner import always_abstain, derive_expected, run, verify
from open_data_analyst.evals.schema import MortgageStep, Question, load_questions
from open_data_analyst.evals.scoring import (
    CORRECT,
    CORRECT_REFUSAL,
    MISSED,
    NO_QUERY,
    OVERREACH,
    WRONG,
    AgentAnswer,
    score,
)


def number(**kwargs):
    base = dict(
        id="q", category="lookup", question="?", answer_type="number", expected=100.0,
        reference_sql="SELECT 100",
    )  # fmt: skip
    return Question(**{**base, **kwargs})


def refusal(**kwargs):
    base = dict(
        id="a", category="abstain", question="?", answer_type="abstain", expected=None,
        why_abstain="not in the data",
    )  # fmt: skip
    return Question(**{**base, **kwargs})


def test_number_tolerance_uses_the_looser_of_absolute_and_relative():
    q = number(abs_tol=0.5, rel_tol=0.01)
    assert score(q, AgentAnswer(100.9, query="SELECT 1")).outcome == CORRECT
    assert score(q, AgentAnswer(101.1, query="SELECT 1")).outcome == WRONG
    assert score(number(), AgentAnswer(100.01, query="SELECT 1")).outcome == WRONG


def test_right_value_without_a_query_is_not_a_pass():
    assert score(number(), AgentAnswer(100.0)).outcome == NO_QUERY


def test_booleans_are_not_numbers_and_text_ignores_case():
    assert score(number(), AgentAnswer(True, query="x")).outcome == WRONG
    text = number(answer_type="text", expected="Vancouver")
    assert score(text, AgentAnswer(" vancouver ", query="x")).outcome == CORRECT
    flag = number(answer_type="bool", expected=True)
    assert score(flag, AgentAnswer(True, query="x")).outcome == CORRECT
    assert score(flag, AgentAnswer("yes", query="x")).outcome == WRONG


def test_refusal_outcomes():
    assert score(refusal(), AgentAnswer(abstained=True)).outcome == CORRECT_REFUSAL
    assert score(refusal(), AgentAnswer(5.0, query="x")).outcome == OVERREACH
    assert score(number(), AgentAnswer(abstained=True)).outcome == MISSED


def test_question_validation():
    with pytest.raises(ValueError, match="exactly when"):
        number(answer_type="abstain")
    with pytest.raises(ValueError, match="reference_sql"):
        number(reference_sql="")
    with pytest.raises(ValueError, match="what the data cannot support"):
        refusal(why_abstain="")
    with pytest.raises(ValueError, match="category"):
        number(category="vibes")


def test_derive_expected_applies_mortgage_and_subtraction():
    con = duckdb.connect()
    q = number(
        reference_sql="SELECT 600000",
        mortgage=MortgageStep(rate_pct=6.19),
        minus_sql="SELECT 2000",
    )
    assert derive_expected(con, q) == pytest.approx(3125.49 - 2000, abs=0.01)


def test_verify_flags_drift_and_marks_volatile_ones(tmp_path):
    db = tmp_path / "t.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE t AS SELECT 101 AS v")
    con.close()
    stable = number(id="stable", reference_sql="SELECT v FROM t")
    volatile = number(id="vol", reference_sql="SELECT v FROM t", volatile=True)
    problems = verify(db, [stable, volatile, refusal()])
    assert [p.split(":")[0] for p in problems] == ["stable", "~vol"]


def test_seed_questions_are_valid_and_the_floor_is_only_refusals():
    questions = load_questions()
    assert len(questions) >= 30
    assert {q.category for q in questions} == {"lookup", "calc", "scope", "abstain"}
    refusals = [q for q in questions if q.answer_type == "abstain"]
    assert 0.2 <= len(refusals) / len(questions) <= 0.4
    report = run(questions, always_abstain)
    assert report.counts[CORRECT_REFUSAL] == len(refusals)
    assert report.confident_wrong == 0
    assert report.counts[MISSED] == len(questions) - len(refusals)
    for line in Path("data/eval/questions.jsonl").read_text().splitlines():
        json.loads(line)  # one JSON object per line


def test_bool_question_with_mortgage_asks_whether_payment_beats_the_subtracted_value():
    con = duckdb.connect()
    base = dict(
        answer_type="bool", expected=True, reference_sql="SELECT 600000",
        mortgage=MortgageStep(rate_pct=6.19),
    )  # fmt: skip
    assert derive_expected(con, number(minus_sql="SELECT 2000", **base)) is True
    assert derive_expected(con, number(minus_sql="SELECT 4000", **base)) is False
