"""Command line: fetch raw data, build the DuckDB store, print the data dictionary.

uv run python -m open_data_analyst.data refresh      # fetch + build
uv run python -m open_data_analyst.data fetch
uv run python -m open_data_analyst.data build
uv run python -m open_data_analyst.data dictionary   # writes docs/data-dictionary.md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from open_data_analyst.data import boc, cmhc, municipalities, schema, statcan_rent, store
from open_data_analyst.data.http import Fetched, raw_dir

SOURCES = (boc, statcan_rent, cmhc, municipalities)
PROVENANCE_FILE = "provenance.json"


def fetch_all(raw: Path) -> list[Fetched]:
    fetched = []
    for module in SOURCES:
        files = module.fetch(raw)
        print(f"{module.SOURCE}: {len(files)} file(s)")
        fetched += files
    (raw / PROVENANCE_FILE).write_text(
        json.dumps(
            [
                {
                    "source": f.source,
                    "url": f.url,
                    "path": str(f.path.relative_to(raw)),
                    "sha256": f.sha256,
                    "fetched_at": f.fetched_at.isoformat(),
                }
                for f in fetched
            ],
            indent=1,
        )
    )
    return fetched


def read_provenance(raw: Path) -> list[Fetched]:
    path = raw / PROVENANCE_FILE
    if not path.exists():
        return []
    return [
        Fetched(
            e["source"],
            e["url"],
            raw / e["path"],
            e["sha256"],
            datetime.fromisoformat(e["fetched_at"]),
        )
        for e in json.loads(path.read_text())
    ]


def build_all(raw: Path, db: Path) -> int:
    counts = store.build(raw, db, read_provenance(raw))
    for name, n in counts.items():
        print(f"{name}: {n:,} rows")
    problems = store.check(db)
    for problem in problems:
        print(f"CHECK: {problem}", file=sys.stderr)
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="open_data_analyst.data")
    parser.add_argument("command", choices=["refresh", "fetch", "build", "dictionary"])
    parser.add_argument("--db", type=Path, default=store.DEFAULT_DB)
    args = parser.parse_args(argv)
    raw = raw_dir()
    if args.command == "dictionary":
        Path("docs/data-dictionary.md").write_text(schema.dictionary_markdown())
        return 0
    if args.command in ("refresh", "fetch"):
        fetch_all(raw)
    if args.command in ("refresh", "build"):
        return build_all(raw, args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
