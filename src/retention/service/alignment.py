"""Temporal alignment: which indicator values each objective row may see (D-28..D-31, D-36..D-38).

Step 1 builds the "analysis units" (one row per objective x country x period) with an as-of date:
    NEW_HIRE_6M       country x hire quarter   as-of = first day of the hire quarter    (D-28)
    SENIOR_HIRE_12M   country x hire year      as-of = 1 January of the hire year       (D-36)
                      country x hire quarter   descriptive only, to show the noise      (D-36)
    REGRETTED_TURNOVER_12M  country x December TTM  as-of = start of the 12-month window (D-37, D-38)
Step 2 joins each unit to the latest indicator values already published on that date.
The join itself is SQL (sql/as_of_join.sql).
"""

from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

from retention.config import Settings
from retention.repository.sql_repository import register_table, run_sql

UNIT_COLUMNS = [
    "objective_id",
    "analysis_set",
    "grain",
    "country_code",
    "period",
    "anchor_date",
    "outcome_rate",
    "cohort_n",
]


def quarter_start(label: str) -> date:
    """ "2023-Q1" -> 2023-01-01, "2023-Q3" -> 2023-07-01."""
    year_text, quarter_text = label.split("-Q")
    first_month = (int(quarter_text) - 1) * 3 + 1
    return date(int(year_text), first_month, 1)


def build_analysis_units(cohorts: pd.DataFrame, turnover: pd.DataFrame) -> pd.DataFrame:
    """One row per objective x country x period that enters the association analysis.

    Only the primary variant, per-country rows with at least one mature hire.
    """
    units = []

    # 1. Hire-retention cohorts.
    is_primary = cohorts["variant"] == "primary"
    is_country = cohorts["scope"] == "country"
    has_mature_hires = cohorts["n"] > 0
    primary = cohorts[is_primary & is_country & has_mature_hires]
    for row in primary.to_dict("records"):
        objective = row["objective_id"]
        grain = row["grain"]
        if objective == "NEW_HIRE_6M" and grain == "quarter":
            analysis_set = "formal"  # D-35 primary, 108 rows
            anchor = quarter_start(row["period"])
        elif objective == "SENIOR_HIRE_12M" and grain == "year":
            analysis_set = "formal"  # D-36: tested at year grain
            anchor = date(int(row["period"]), 1, 1)
        elif objective == "SENIOR_HIRE_12M" and grain == "quarter":
            analysis_set = "descriptive"  # D-36: shown to illustrate noise, never tested
            anchor = quarter_start(row["period"])
        else:
            continue
        units.append(
            {
                "objective_id": objective,
                "analysis_set": analysis_set,
                "grain": grain,
                "country_code": row["country_code"],
                "period": row["period"],
                "anchor_date": anchor,
                "outcome_rate": row["rate"],
                "cohort_n": float(row["n"]),
            }
        )

    # 2. Regretted turnover: December values only (non-overlapping windows, D-37),
    #    anchored at the start of the 12-month window (D-38): Dec-2024 TTM -> 2024-01-01.
    december = turnover[
        (turnover["variant"] == "primary") & (turnover["scope"] == "country") & turnover["is_year_end"]
    ]
    for row in december.to_dict("records"):
        year = row["month_end"].year
        units.append(
            {
                "objective_id": "REGRETTED_TURNOVER_12M",
                "analysis_set": "formal",
                "grain": "year_end_ttm",
                "country_code": row["country_code"],
                "period": str(year),
                "anchor_date": date(year, 1, 1),
                "outcome_rate": row["rate"],
                "cohort_n": float(row["avg_headcount"]),  # denominator = average headcount
            }
        )

    return pd.DataFrame(units, columns=UNIT_COLUMNS)


def align_indicators(con: duckdb.DuckDBPyConnection, units: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Run the as-of join and mark rows excluded from formal tests (IE GDP, D-59).

    `con` must already have the canonical `indicators` view.
    """
    register_table(con, "analysis_units", units)
    lags = settings.publication_lag_months
    aligned = run_sql(
        con,
        "as_of_join",
        {"lag_monthly": lags["monthly"], "lag_quarterly": lags["quarterly"], "lag_annual": lags["annual"]},
    )

    # D-59: data kept and shown; only the association test for that indicator skips these countries.
    excluded = []
    reasons = []
    for row in aligned.to_dict("records"):
        indicator_settings = settings.indicators[row["indicator"]]
        if row["country_code"] in indicator_settings.exclude_from_analysis:
            excluded.append(True)
            reasons.append(f"{row['country_code']} excluded from {row['indicator']} tests (D-59)")
        elif pd.isna(row["value"]):
            excluded.append(True)
            reasons.append("no published value yet on the as-of date")
        else:
            excluded.append(False)
            reasons.append(None)
    # Whole months, but kept as float so a missing age (no value published yet) can be NaN.
    aligned["age_months"] = aligned["age_months"].astype(float)
    aligned["excluded_from_tests"] = excluded
    aligned["exclusion_reason"] = pd.Series(reasons, dtype="string")
    return aligned
