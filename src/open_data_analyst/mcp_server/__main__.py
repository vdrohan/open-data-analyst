"""Run the MCP server on stdio: uv run python -m open_data_analyst.mcp_server"""

import argparse
from pathlib import Path

from open_data_analyst.data.store import DEFAULT_DB
from open_data_analyst.mcp_server.server import DEFAULT_ASK_BUDGET_USD, build_server


def main() -> None:
    parser = argparse.ArgumentParser(prog="open_data_analyst.mcp_server")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--ask-budget", type=float, default=DEFAULT_ASK_BUDGET_USD)
    args = parser.parse_args()
    build_server(args.db.resolve(), ask_budget_usd=args.ask_budget).run("stdio")


if __name__ == "__main__":
    main()
