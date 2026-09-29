"""Objective metrics: SQL counts -> rates, Wilson CIs, targets and status (D-16..D-23, D-75..D-78).

Spring analogy: a @Service that calls the repository (SQL) and applies the presentation rules.

SQL does the counting (who is in the cohort, who stayed, who left, headcounts).
Python adds, per row:
    rate           retained / n              (turnover: regretted exits / average headcount)
    ci_low/high    95% Wilson interval       (D-33)
    target         from the objectives table (canonical/objectives.parquet)
    status         met / not_met / inconclusive, ONLY on verdict rows (D-75, D-76)
    small_sample   n < 10                    (D-78)
"""

from __future__ import annotations

import duckdb
import pandas as pd

from retention.config import Settings
from retention.domain.errors import CurationError
from retention.repository.sql_repository import register_table, run_sql
from retention.service.stats import objective_status, wilson_interval

VERDICT_GRAINS = ["year", "period"]  # D-76: quarters are trend lines only
RATE_FIELDS = ["rate", "ci_low", "ci_high", "target", "direction", "status", "small_sample"]
TURNOVER_OBJECTIVE = "REGRETTED_TURNOVER_12M"


def period_label(settings: Settings) -> str:
    """The objectives' effective period, e.g. "2021-2025"."""
    return f"{settings.metrics.report_start.year}-{settings.as_of_date.year}"


def sql_params(settings: Settings) -> dict:
    return {"report_start": settings.metrics.report_start, "as_of": settings.as_of_date}


# ---------------------------------------------------------------------------------------------
# Hire-level table and hire-retention cohorts (NEW_HIRE_6M, SENIOR_HIRE_12M)
# ---------------------------------------------------------------------------------------------


def check_senior_levels(senior_levels: list[str], known_levels: list[str]) -> None:
    """D-94: every configured senior level must be a real canonical career level.

    A typo such as "Senior Leaders" would otherwise give zero senior hires without any error.
    """
    if len(senior_levels) == 0:
        raise CurationError("settings.yaml metrics.senior_levels must list at least one career level (D-94)")
    for level in senior_levels:
        if level not in known_levels:
            raise CurationError(
                f"settings.yaml metrics.senior_levels: '{level}' is not a career level "
                f"(known: {', '.join(sorted(known_levels))}) (D-94)"
            )


def compute_hire_outcomes(con: duckdb.DuckDBPyConnection, settings: Settings) -> pd.DataFrame:
    """One row per hire and objective with its outcome (retained / not_retained / immature)."""
    params = sql_params(settings)
    params["senior_levels"] = settings.metrics.senior_levels  # D-94: who counts as senior
    return run_sql(con, "hire_outcomes", params)


def compute_retention_cohorts(
    con: duckdb.DuckDBPyConnection,
    hire_outcomes: pd.DataFrame,
    objectives: pd.DataFrame,
    settings: Settings,
    whole_period: str | None = None,
) -> pd.DataFrame:
    """Count per objective x variant x grain x scope x period, then add rate, CI, target and status.

    The same function serves the API later: it can pass a filtered hire_outcomes table (D-77),
    and a `whole_period` label (e.g. "2022-2023") when it has kept only some hire years (D-90).
    """
    # 1. Counting in SQL.
    register_table(con, "hire_outcomes", hire_outcomes)
    label = whole_period if whole_period is not None else period_label(settings)
    cohorts = run_sql(con, "retention_cohorts", {"period_label": label})

    # 2. Rates, intervals, targets and status in Python.
    targets = _targets(objectives)
    rows = []
    for row in cohorts.to_dict("records"):
        target, direction = targets[row["objective_id"]]
        is_verdict_row = row["grain"] in VERDICT_GRAINS
        row.update(_rate_fields(row["retained"], row["n"], target, direction, is_verdict_row, settings))
        rows.append(row)
    # Explicit columns: an empty slice (e.g. a segment with no hires) still has the full shape.
    return pd.DataFrame(rows, columns=list(cohorts.columns) + RATE_FIELDS)


# ---------------------------------------------------------------------------------------------
# Regretted turnover (REGRETTED_TURNOVER_12M)
# ---------------------------------------------------------------------------------------------


def compute_regretted_turnover(
    con: duckdb.DuckDBPyConnection, objectives: pd.DataFrame, settings: Settings
) -> pd.DataFrame:
    """Monthly TTM regretted turnover per variant and scope, with CI; verdicts on December rows only."""
    turnover = run_sql(con, "regretted_turnover", sql_params(settings))

    target, direction = _targets(objectives)[TURNOVER_OBJECTIVE]
    rows = []
    for row in turnover.to_dict("records"):
        # D-37 / D-76: a verdict only for the December value of each year (non-overlapping windows).
        is_verdict_row = bool(row["is_year_end"])
        row.update(
            _rate_fields(
                row["regretted_exits"], row["avg_headcount"], target, direction, is_verdict_row, settings
            )
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=list(turnover.columns) + RATE_FIELDS)


# ---------------------------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------------------------


def _targets(objectives: pd.DataFrame) -> dict[str, tuple[float, str]]:
    """{"NEW_HIRE_6M": (0.86, "at_least"), ...} from canonical/objectives."""
    targets = {}
    for row in objectives.to_dict("records"):
        targets[row["objective_id"]] = (float(row["target_value"]), row["direction"])
    return targets


def _rate_fields(
    successes: float, n: float, target: float, direction: str, is_verdict_row: bool, settings: Settings
) -> dict:
    """rate, ci_low, ci_high, target, direction, status, small_sample for one row.

    Example: successes=12, n=16, target 0.86 at_least, verdict row
          -> rate 0.75, CI [0.505, 0.898], status "inconclusive", small_sample False
    """
    fields = {
        "rate": None,
        "ci_low": None,
        "ci_high": None,
        "target": target,
        "direction": direction,
        "status": None,
        "small_sample": bool(n < settings.metrics.small_sample_below),  # D-78
    }
    if n <= 0:
        return fields  # e.g. a 2025 senior cohort: nobody has completed 12 months yet

    interval = wilson_interval(successes, n, settings.metrics.confidence_level)
    fields["rate"] = successes / n
    fields["ci_low"] = interval[0]
    fields["ci_high"] = interval[1]
    if is_verdict_row:
        fields["status"] = objective_status(interval[0], interval[1], target, direction)
    return fields
