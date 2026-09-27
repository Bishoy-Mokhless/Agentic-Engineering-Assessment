"""Association analysis: do external indicators move with retention?

Decisions: D-32..D-35, D-54..D-56, D-63, D-79, D-80.

Spring analogy: a @Service with pure functions (easy to unit test).

For each objective x indicator, three views of Spearman rank correlation:
    within_country  FORMAL   subtract each country's average first, so only movement over time inside
                             a country is compared (D-54). One Holm family of 4 tests per objective (D-55).
    pooled          descriptive  all rows together; mixes "countries differ" with "things change" (D-54)
    time_adjusted   descriptive  subtract country AND period averages: a confounding check (D-79)
Each result has: rho (effect), 95% bootstrap CI (exploratory, D-56), n, p-value (+ Holm-adjusted for
formal rows), and D-63 wording that never claims causation or proof of no relationship.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

from retention.config import Settings

FORMAL_VIEW = "within_country"
VIEWS = ["within_country", "pooled", "time_adjusted"]

# D-35 / D-63 labels, shown with every result.
OBJECTIVE_LABELS = {
    "NEW_HIRE_6M": "NEW_HIRE_6M — Primary association analysis",
    "SENIOR_HIRE_12M": "SENIOR_HIRE_12M — Secondary sensitivity analysis (low power)",
    "REGRETTED_TURNOVER_12M": (
        "REGRETTED_TURNOVER_12M — Secondary sensitivity analysis (overlapping TTM windows)"
    ),
}
OBJECTIVE_CAVEATS = {
    "NEW_HIRE_6M": "Country-quarter cohorts of 7-29 people; the same country appears in many rows over time.",
    "SENIOR_HIRE_12M": (
        "Low power: about 11 senior hires per country-year, so one or two people move a rate by 5-20 points."
    ),
    "REGRETTED_TURNOVER_12M": (
        "Monthly TTM values overlap, so only December values are tested: 5 per country, small numerators."
    ),
}
VIEW_WORDING = {
    "pooled": "Descriptive pooled context — not the primary formal test.",
    "time_adjusted": (
        "Descriptive time-adjusted check (country and period averages removed) — not a formal test."
    ),
}
COMMON_CAVEAT = (
    "Associative, not causal. Bootstrap interval is exploratory: rows are not independent (D-56). "
    "Each row counts once regardless of its size (D-80)."
)


# ---------------------------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------------------------


def demean(values: list[float], groups: list[str]) -> list[float]:
    """Subtract each group's average.

    Example: values [1, 3, 10, 14], groups [A, A, B, B] -> [-1, 1, -2, 2]
    """
    totals = {}
    counts = {}
    for value, group in zip(values, groups, strict=True):
        totals[group] = totals.get(group, 0.0) + value
        counts[group] = counts.get(group, 0) + 1

    result = []
    for value, group in zip(values, groups, strict=True):
        result.append(value - totals[group] / counts[group])
    return result


def view_values(x: list[float], y: list[float], countries: list[str], periods: list[str], view: str):
    """Transform (indicator, outcome) for one view before ranking."""
    if view == "pooled":
        return x, y
    within_x = demean(x, countries)
    within_y = demean(y, countries)
    if view == "within_country":
        return within_x, within_y
    if view == "time_adjusted":
        return demean(within_x, periods), demean(within_y, periods)
    raise ValueError(f"unknown view '{view}' (expected one of {VIEWS})")


def spearman_rho(x: list[float], y: list[float]) -> float:
    """Spearman rho = Pearson correlation of the ranks (ties get average ranks). NaN if a side is constant."""
    if len(x) < 3:
        return math.nan
    rank_x = rankdata(x)
    rank_y = rankdata(y)
    if np.std(rank_x) == 0 or np.std(rank_y) == 0:
        return math.nan
    return float(np.corrcoef(rank_x, rank_y)[0, 1])


def spearman_with_p(x: list[float], y: list[float]) -> tuple[float, float]:
    """rho and its two-sided p-value (scipy). NaN, NaN when it cannot be computed."""
    rho = spearman_rho(x, y)
    if math.isnan(rho):
        return math.nan, math.nan
    result = spearmanr(x, y)
    return float(result.statistic), float(result.pvalue)


def bootstrap_interval(
    rows: pd.DataFrame, view: str, iterations: int, seed: int
) -> tuple[float | None, float | None]:
    """95% percentile interval of rho: resample rows with replacement, redo the SAME view each time.

    Exploratory only (D-56): a row bootstrap assumes independent rows, which ours are not,
    so the interval is probably too narrow.
    """
    rng = np.random.default_rng(seed)  # fixed seed -> deterministic reruns (D-48)
    x = rows["value"].to_numpy()
    y = rows["outcome_rate"].to_numpy()
    countries = rows["country_code"].to_numpy()
    periods = rows["period"].to_numpy()
    size = len(rows)

    estimates = []
    for _ in range(iterations):
        picked = rng.integers(0, size, size)
        sample_x, sample_y = view_values(
            list(x[picked]), list(y[picked]), list(countries[picked]), list(periods[picked]), view
        )
        rho = spearman_rho(sample_x, sample_y)
        if not math.isnan(rho):
            estimates.append(rho)

    if len(estimates) < iterations / 2:
        return None, None  # too many degenerate resamples to say anything
    return float(np.percentile(estimates, 2.5)), float(np.percentile(estimates, 97.5))


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm step-down adjustment (D-34, D-55).

    Sort p-values from smallest to largest; multiply the k-th smallest by (m - k + 1); never let an
    adjusted value be smaller than the one before it; cap at 1.
    Example: [0.01, 0.04, 0.03, 0.20] -> [0.04, 0.09, 0.09, 0.20]
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, index in enumerate(order):
        value = min(1.0, (m - rank) * p_values[index])
        running_max = max(running_max, value)
        adjusted[index] = running_max
    return adjusted


def time_trend_rho(rows: pd.DataFrame) -> float:
    """D-79 diagnostic: how strongly the indicator itself moves with time inside countries."""
    time_order = []
    for anchor in rows["anchor_date"]:
        time_order.append(float(anchor.toordinal()))
    countries = list(rows["country_code"])
    return spearman_rho(demean(list(rows["value"]), countries), demean(time_order, countries))


# ---------------------------------------------------------------------------------------------
# The whole analysis
# ---------------------------------------------------------------------------------------------


def run_association(aligned: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """One result row per objective x indicator x view."""
    analysis = settings.analysis
    formal_rows = aligned[(aligned["analysis_set"] == "formal") & ~aligned["excluded_from_tests"]]
    results = []

    for objective_id in analysis.objectives:
        objective_rows = formal_rows[formal_rows["objective_id"] == objective_id]
        role = analysis.objectives[objective_id].role

        for indicator in settings.indicators:
            rows = objective_rows[objective_rows["indicator"] == indicator].sort_values(
                ["country_code", "anchor_date"]
            )
            all_rows = aligned[
                (aligned["analysis_set"] == "formal")
                & (aligned["objective_id"] == objective_id)
                & (aligned["indicator"] == indicator)
            ]
            excluded_countries = sorted(set(all_rows["country_code"]) - set(rows["country_code"]))
            trend = time_trend_rho(rows)

            for view in VIEWS:
                x, y = view_values(
                    list(rows["value"]),
                    list(rows["outcome_rate"]),
                    list(rows["country_code"]),
                    list(rows["period"]),
                    view,
                )
                rho, p_value = spearman_with_p(x, y)
                ci_low, ci_high = bootstrap_interval(
                    rows, view, analysis.bootstrap_iterations, analysis.random_seed
                )
                results.append(
                    {
                        "objective_id": objective_id,
                        "objective_role": role,
                        "label": OBJECTIVE_LABELS[objective_id],
                        "indicator": indicator,
                        "lens": settings.indicators[indicator].lens,
                        "view": view,
                        "is_formal": view == FORMAL_VIEW,
                        "rho": rho,
                        "ci_low": ci_low,
                        "ci_high": ci_high,
                        "p_value": p_value,
                        "p_holm": None,  # filled below for formal rows
                        "n_rows": len(rows),
                        "n_countries": rows["country_code"].nunique(),
                        "countries_excluded": ", ".join(excluded_countries),
                        "indicator_time_rho": trend,
                        "distinct_indicator_values": int(rows["value"].nunique()),
                    }
                )

    table = pd.DataFrame(results)
    table = _add_holm(table)
    table = _add_wording(table, analysis.alpha)
    return table


def _add_holm(table: pd.DataFrame) -> pd.DataFrame:
    """Holm-adjust each objective's formal family (4 within-country tests, D-55)."""
    table = table.copy()
    table["holm_family_size"] = 0
    for objective_id in table["objective_id"].unique():
        family = table[
            (table["objective_id"] == objective_id) & table["is_formal"] & table["p_value"].notna()
        ]
        adjusted = holm_adjust(list(family["p_value"]))
        for index, value in zip(family.index, adjusted, strict=True):
            table.loc[index, "p_holm"] = value
            table.loc[index, "holm_family_size"] = len(family)
    table["p_holm"] = table["p_holm"].astype(float)
    return table


def _add_wording(table: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """D-63: allowed wording only. Never 'proves', never 'causes'."""
    results = []
    caveats = []
    for row in table.to_dict("records"):
        if not row["is_formal"]:
            result = VIEW_WORDING[row["view"]]
        elif math.isnan(row["p_value"]):
            result = "Could not be computed (too few rows or no variation)."
        elif row["p_holm"] < alpha:
            result = f"Association in this sample (Holm-adjusted p < {alpha}). Associative, not causal."
        else:
            result = "The analysis did not show a clear association in this sample."
        results.append(result)

        caveat = OBJECTIVE_CAVEATS[row["objective_id"]] + " " + COMMON_CAVEAT
        if row["countries_excluded"]:
            caveat += f" Excluded from this test: {row['countries_excluded']} (D-59)."
        if row["distinct_indicator_values"] <= row["n_rows"] / 2:
            caveat += (
                f" Only {row['distinct_indicator_values']} distinct indicator values across "
                f"{row['n_rows']} rows (carried forward or rounded values repeat)."
            )
        if abs(row["indicator_time_rho"]) >= 0.5:
            caveat += (
                " The indicator trends strongly with time within countries"
                f" (rho {row['indicator_time_rho']:+.2f}): time is a plausible confounder (D-79)."
            )
        caveats.append(caveat)

    table = table.copy()
    table["result"] = results
    table["caveat"] = caveats
    return table
