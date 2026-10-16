"""Command line for the eval set.

uv run python -m open_data_analyst.evals verify     # re-derive expected answers from the data
uv run python -m open_data_analyst.evals baseline   # score the always-abstain floor
"""

import argparse
from pathlib import Path

from open_data_analyst.data.store import DEFAULT_DB
from open_data_analyst.evals.runner import always_abstain, run, verify
from open_data_analyst.evals.schema import DEFAULT_PATH, load_questions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="open_data_analyst.evals")
    parser.add_argument("command", choices=["verify", "baseline"])
    parser.add_argument("--questions", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)
    questions = load_questions(args.questions)
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
