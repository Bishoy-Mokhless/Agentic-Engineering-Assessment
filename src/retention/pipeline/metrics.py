"""Metrics step: canonical -> analytical (D-03, D-41, D-77).

Spring analogy: one Step of a Spring Batch Job; it only orchestrates.

Reads the canonical tables built earlier in the SAME run (inside the build folder, not yet
published), and writes three analytical tables:
    hire_outcomes       one row per hire and objective (feature table; the API filters it, D-77)
    retention_cohorts   NEW_HIRE_6M / SENIOR_HIRE_12M counts, rates, CIs, status
    regretted_turnover  monthly TTM regretted turnover, rates, CIs, status on December rows
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from retention.config import Settings
from retention.domain import schemas
from retention.repository.curated_repository import CuratedRepository, TableInfo
from retention.repository.sql_repository import open_connection
from retention.service.metrics import (
    compute_hire_outcomes,
    compute_regretted_turnover,
    compute_retention_cohorts,
)

log = logging.getLogger(__name__)


def run_metrics(settings: Settings, curated_repo: CuratedRepository, build: Path) -> dict[str, TableInfo]:
    """Build the analytical metric tables into `build`. Returns what was written (for _build.json)."""
    canonical = curated_repo.layer_path(build, "canonical")
    con = open_connection(
        {
            "employees": canonical / "employees.parquet",
            "objectives": canonical / "objectives.parquet",
        }
    )
    objectives = pd.read_parquet(canonical / "objectives.parquet")
    written = {}

    # 1. Hire-level outcomes (feature table).
    hire_outcomes = compute_hire_outcomes(con, settings)
    schemas.check_contract(schemas.HIRE_OUTCOMES, hire_outcomes, "analytical hire_outcomes")
    written["hire_outcomes"] = curated_repo.write_table(build, "analytical", "hire_outcomes", hire_outcomes)

    # 2. Hire-retention cohorts (NEW_HIRE_6M, SENIOR_HIRE_12M).
    cohorts = compute_retention_cohorts(con, hire_outcomes, objectives, settings)
    schemas.check_contract(schemas.RETENTION_COHORTS, cohorts, "analytical retention_cohorts")
    written["retention_cohorts"] = curated_repo.write_table(build, "analytical", "retention_cohorts", cohorts)

    # 3. Regretted turnover (REGRETTED_TURNOVER_12M).
    turnover = compute_regretted_turnover(con, objectives, settings)
    schemas.check_contract(schemas.REGRETTED_TURNOVER, turnover, "analytical regretted_turnover")
    written["regretted_turnover"] = curated_repo.write_table(
        build, "analytical", "regretted_turnover", turnover
    )

    con.close()
    _log_headlines(cohorts, turnover)
    return written


def _log_headlines(cohorts: pd.DataFrame, turnover: pd.DataFrame) -> None:
    """Print the company-level verdicts for the whole period, so a run shows the key numbers."""
    company_period = cohorts[
        (cohorts["variant"] == "primary") & (cohorts["scope"] == "company") & (cohorts["grain"] == "period")
    ]
    for row in company_period.to_dict("records"):
        log.info(
            "Metrics %-16s %s: %d/%d = %.1f%% [%.1f%%, %.1f%%] target %.0f%% -> %s",
            row["objective_id"],
            row["period"],
            row["retained"],
            row["n"],
            row["rate"] * 100,
            row["ci_low"] * 100,
            row["ci_high"] * 100,
            row["target"] * 100,
            row["status"],
        )

    december = turnover[
        (turnover["variant"] == "primary") & (turnover["scope"] == "company") & turnover["is_year_end"]
    ]
    for row in december.to_dict("records"):
        log.info(
            "Metrics REGRETTED_TURNOVER_12M %s: %d / %.0f = %.2f%% target %.1f%% -> %s",
            row["month_end"].strftime("%Y-%m"),
            row["regretted_exits"],
            row["avg_headcount"],
            row["rate"] * 100,
            row["target"] * 100,
            row["status"],
        )
