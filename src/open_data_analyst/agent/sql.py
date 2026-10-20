"""Read-only SQL over the DuckDB store, with row and time limits.

Three independent guards, so no single mistake gives the agent write access:
the connection is opened read-only, file and network access is switched off and the
configuration locked, and only a single SELECT statement is accepted.
"""

import threading
from dataclasses import dataclass
from pathlib import Path

import duckdb

MAX_ROWS = 50
TIMEOUT_SECONDS = 10.0


class SQLRefused(Exception):
    """The statement was not allowed or did not run. The message is safe to show the model."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool  # more rows existed than MAX_ROWS

    def as_text(self) -> str:
        lines = [" | ".join(self.columns)]
        lines += [" | ".join("NULL" if v is None else str(v) for v in row) for row in self.rows]
        if self.truncated:
            lines.append(f"(showing the first {len(self.rows)} rows; there are more)")
        elif not self.rows:
            lines.append("(no rows)")
        return "\n".join(lines)


class ReadOnlyStore:
    def __init__(
        self, db_path: Path, max_rows: int = MAX_ROWS, timeout: float = TIMEOUT_SECONDS
    ) -> None:
        self.max_rows = max_rows
        self.timeout = timeout
        self._con = duckdb.connect(
            str(db_path),
            read_only=True,
            config={"enable_external_access": False, "lock_configuration": True},
        )

    def close(self) -> None:
        self._con.close()

    def query(self, sql: str) -> QueryResult:
        sql = sql.strip().rstrip(";").strip()
        if not sql:
            raise SQLRefused("empty query")
        try:
            statements = self._con.extract_statements(sql)
        except duckdb.Error as exc:
            raise SQLRefused(f"could not parse the query: {exc}") from exc
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise SQLRefused("only a single SELECT (or WITH ... SELECT) statement is allowed")

        # A cursor per query so an interrupt cannot disturb anything else.
        cursor = self._con.cursor()
        timer = threading.Timer(self.timeout, cursor.interrupt)
        timer.start()
        try:
            cursor.execute(sql)
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchmany(self.max_rows + 1)
        except duckdb.InterruptException as exc:
            raise SQLRefused(f"query stopped after {self.timeout:g}s; make it cheaper") from exc
        except duckdb.Error as exc:
            raise SQLRefused(f"query failed: {exc}") from exc
        finally:
            timer.cancel()
            cursor.close()
        return QueryResult(columns, rows[: self.max_rows], len(rows) > self.max_rows)

    def schema_text(self) -> str:
        """Every table with its description and columns (the comments written at build time)."""
        tables = self._con.execute(
            "SELECT table_name, comment FROM duckdb_tables() ORDER BY table_name"
        ).fetchall()
        columns = self._con.execute(
            "SELECT table_name, column_name, data_type, comment FROM duckdb_columns() "
            "ORDER BY table_name, column_index"
        ).fetchall()
        out = []
        for name, comment in tables:
            out.append(f"TABLE {name}: {comment or ''}")
            out += [f"  {c} {t}: {d or ''}" for tn, c, t, d in columns if tn == name]
            out.append("")
        return "\n".join(out).strip()
