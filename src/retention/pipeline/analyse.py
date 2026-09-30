"""Analyse step: as-of join + association analysis -> analytical layer (D-28..D-31, D-54..D-56, D-79).

Reads, from the SAME build: canonical/indicators and analytical/retention_cohorts + regretted_turnover.
Writes:
    aligned_observations   one row per objective x country x period x indicator: the value known on
                           the as-of date, with its source period, frequency, age and status (D-31)
    association_results    one row per objective x indicator x view: rho, CI, n, p, Holm p, wording
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from retention.config import Settings
from retention.domain import schemas
from retention.repository.curated_repository import CuratedRepository, TableInfo
from retention.repository.sql_repository import open_connection
from retention.service.alignment import align_indicators, build_analysis_units
from retention.service.association import run_association

log = logging.getLogger(__name__)


def run_analysis(settings: Settings, curated_repo: CuratedRepository, build: Path) -> dict[str, TableInfo]:
    canonical = curated_repo.layer_path(build, "canonical")
    analytical = curated_repo.layer_path(build, "analytical")
    written = {}

    # 1. Which rows are analysed, and their as-of dates.
    cohorts = pd.read_parquet(analytical / "retention_cohorts.parquet")
    turnover = pd.read_parquet(analytical / "regretted_turnover.parquet")
    units = build_analysis_units(cohorts, turnover)

    # 2. As-of join: only values already published on each as-of date.
    con = open_connection({"indicators": canonical / "indicators.parquet"})
    aligned = align_indicators(con, units, settings)
    con.close()
    schemas.check_contract(schemas.ALIGNED_OBSERVATIONS, aligned, "analytical aligned_observations")
    written["aligned_observations"] = curated_repo.write_table(
        build, "analytical", "aligned_observations", aligned
    )

    # 3. Association analysis.
    results = run_association(aligned, settings)
    schemas.check_contract(schemas.ASSOCIATION_RESULTS, results, "analytical association_results")
    written["association_results"] = curated_repo.write_table(
        build, "analytical", "association_results", results
    )

    _log_formal_results(results)
    return written


def _log_formal_results(results: pd.DataFrame) -> None:
    formal = results[results["is_formal"]]
    for row in formal.to_dict("records"):
        log.info(
            "Association %-22s %-12s rho %+.2f [%+.2f, %+.2f] n=%-3d p_holm %.2f -> %s",
            row["objective_id"],
            row["indicator"],
            row["rho"],
            row["ci_low"],
            row["ci_high"],
            row["n_rows"],
            row["p_holm"],
            row["result"],
        )
