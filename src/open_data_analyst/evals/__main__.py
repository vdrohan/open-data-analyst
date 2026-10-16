"""Command line for the eval set.

uv run python -m open_data_analyst.evals verify     # re-derive expected answers from the data
uv run python -m open_data_analyst.evals baseline   # score the always-abstain floor
uv run python -m open_data_analyst.evals agent      # score the Claude agent (needs a key)
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from open_data_analyst.agent.loop import DEFAULT_MODEL, Agent, BudgetExceeded
from open_data_analyst.data.store import DEFAULT_DB
from open_data_analyst.evals.runner import always_abstain, run, verify
from open_data_analyst.evals.schema import DEFAULT_PATH, load_questions


def _run_agent(args: argparse.Namespace, questions: list) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; the agent cannot call Claude.", file=sys.stderr)
        return 2
    import anthropic

    if args.only:
        questions = [q for q in questions if q.id in set(args.only)]
    agent = Agent(anthropic.Anthropic(), args.db, args.model, max_cost_usd=args.max_cost)
    try:
        report = run(questions, agent)
    except BudgetExceeded as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        report = None
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = args.runs_dir / f"{stamp}-{args.model}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for log in agent.logs:
            row = log.to_json()
            if report and log.question_id in report.results:
                row["outcome"] = report.results[log.question_id].outcome
                row["detail"] = report.results[log.question_id].detail
            handle.write(json.dumps(row) + "\n")
    if report:
        print(report.summary())
    n = len(agent.logs)
    print(
        f"model {args.model}: {n} questions, ${agent.total_cost_usd:.4f} total, "
        f"${agent.total_cost_usd / max(n, 1):.4f} per question; traces in {path}"
    )
    return 0 if report else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="open_data_analyst.evals")
    parser.add_argument("command", choices=["verify", "baseline", "agent"])
    parser.add_argument("--questions", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="agent: model id")
    parser.add_argument("--max-cost", type=float, default=1.0, help="agent: stop at this USD spend")
    parser.add_argument("--only", nargs="*", help="agent: run just these question ids")
    parser.add_argument("--runs-dir", type=Path, default=Path("data/eval/runs"))
    args = parser.parse_args(argv)
    questions = load_questions(args.questions)
    if args.command == "agent":
        return _run_agent(args, questions)
    if args.command == "baseline":
        print(run(questions, always_abstain).summary())
        return 0
    problems = verify(args.db, questions)
    for problem in problems:
        print(problem)
    hard = [p for p in problems if not p.startswith("~")]
    print(
        f"{len(questions)} questions, {len(hard)} mismatches, {len(problems) - len(hard)} drifted"
    )
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
