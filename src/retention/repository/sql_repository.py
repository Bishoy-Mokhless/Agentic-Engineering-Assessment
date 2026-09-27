"""Run the metric SQL files with DuckDB on Parquet tables (D-03, D-41).

Spring analogy: a @Repository using JdbcTemplate, with the queries kept in .sql resource files
(like queries in src/main/resources) so they can be read and reviewed on their own.

Example:
    con = open_connection({"employees": Path("data/curated/canonical/employees.parquet")})
    table = run_sql(con, "hire_outcomes", {"report_start": date(2021, 1, 1), "as_of": date(2025, 12, 31)})
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import duckdb
import pandas as pd


def load_sql(name: str) -> str:
    """Text of src/retention/sql/<name>.sql (packaged with the code)."""
    return resources.files("retention").joinpath("sql", f"{name}.sql").read_text(encoding="utf-8")


def open_connection(tables: dict[str, Path]) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB with one view per Parquet file, e.g. view `employees` -> employees.parquet."""
    con = duckdb.connect()
    for view_name, path in tables.items():
        if not path.exists():
            raise FileNotFoundError(f"input table for view '{view_name}' not found: {path}")
        location = path.as_posix().replace("'", "''")
        con.execute(f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{location}')")
    return con


def register_table(con: duckdb.DuckDBPyConnection, view_name: str, table: pd.DataFrame) -> None:
    """Make a pandas table queryable by name, e.g. the hire_outcomes result for the cohort query."""
    con.register(view_name, table)


def run_sql(con: duckdb.DuckDBPyConnection, name: str, params: dict | None = None) -> pd.DataFrame:
    """Run one .sql file with named parameters ($report_start, $as_of, ...) and return a pandas table.

    Goes through Arrow so DATE columns stay real dates (pandas' .df() would turn them into timestamps).
    """
    sql = load_sql(name)
    if params is None:
        params = {}
    arrow_table = con.execute(sql, params).to_arrow_table()
    return arrow_table.to_pandas(date_as_object=True)
