"""Quality and coverage report for the canonical layer (brief: "quality/coverage report").

Read later by /api/quality and the dashboard's Trust view.

It answers four questions:
    1. Reconciliation: do the row counts add up from source to canonical?   (a quality gate)
    2. What was flagged, how many rows, what happened to them, which decision?
    3. How are the special values distributed (UNKNOWN, NOT_APPLICABLE, ...)?
    4. Coverage: per indicator and country, first/last period, gaps, provisional values.
"""

from __future__ import annotations

import pandas as pd

from retention.domain.errors import CurationError
from retention.domain.quality import FLAG_RULES, Flag, MetricStatus
from retention.service.hr_curation import HrCurationResult
from retention.service.indicator_curation import IndicatorCurationResult


def build_quality_report(
    hr: HrCurationResult,
    indicator_results: dict[str, IndicatorCurationResult],
    indicators: pd.DataFrame,
) -> dict:
    """Return the report as plain dicts/lists (JSON-friendly).

    Raises CurationError if the row counts do not reconcile (rows were lost or invented).
    """
    return {
        "hr": _hr_section(hr),
        "indicators": {
            "reconciliation": _indicator_reconciliation(indicator_results),
            "coverage": _coverage(indicators),
        },
    }


# ---------------------------------------------------------------------------------------------
# HR
# ---------------------------------------------------------------------------------------------


def _hr_section(hr: HrCurationResult) -> dict:
    employees = hr.employees
    issues = hr.issues

    # 1. Reconciliation: rows in the file - removed repeats = employees out.
    expected = hr.rows_in - hr.duplicates_removed
    if expected != len(employees):
        raise CurationError(
            f"HR reconciliation failed: {hr.rows_in} rows - {hr.duplicates_removed} removed "
            f"= {expected}, but {len(employees)} employees were produced"
        )
    reconciliation = {
        "rows_in_file": hr.rows_in,
        "duplicate_rows_removed": hr.duplicates_removed,
        "employees_out": len(employees),
        "balanced": True,
    }

    # 2. Employees per metric status (always list all three, even when zero).
    status_counts = {}
    for status in MetricStatus:
        status_counts[status.value] = int((employees["metric_status"] == status.value).sum())

    # 3. One line per flag, with what it does and why.
    flag_lines = []
    for flag in Flag:
        rule = FLAG_RULES[flag]
        flag_lines.append(
            {
                "flag": flag.value,
                "rows": int((issues["flag"] == flag.value).sum()),
                "effect": rule.effect.value,
                "decision": rule.decision,
                "meaning": rule.meaning,
            }
        )

    return {
        "reconciliation": reconciliation,
        "metric_status": status_counts,
        "flags": flag_lines,
        "termination_type": _counts(employees["termination_type"]),
        "regretted_exit": _counts(employees["regretted_exit"]),
        "country_code": _counts(employees["country_code"]),
    }


def _counts(column: pd.Series) -> dict[str, int]:
    """{"TRUE": 240, "FALSE": 525, ...}, sorted by value so the file is stable."""
    counts = column.value_counts()
    result = {}
    for value in sorted(counts.index):
        result[str(value)] = int(counts[value])
    return result


# ---------------------------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------------------------


def _indicator_reconciliation(results: dict[str, IndicatorCurationResult]) -> list[dict]:
    """source rows - rows without a value = canonical rows, per indicator."""
    lines = []
    for name in sorted(results):
        result = results[name]
        expected = result.source_rows - result.missing_values_dropped
        if expected != len(result.rows):
            raise CurationError(
                f"{name} reconciliation failed: {result.source_rows} source rows - "
                f"{result.missing_values_dropped} without value = {expected}, "
                f"but {len(result.rows)} canonical rows were produced"
            )
        lines.append(
            {
                "indicator": name,
                "source_rows": result.source_rows,
                "missing_values_dropped": result.missing_values_dropped,
                "canonical_rows": len(result.rows),
                "balanced": True,
            }
        )
    return lines


def _coverage(indicators: pd.DataFrame) -> list[dict]:
    """Per indicator and country: first/last period, observations, gaps, provisional values.

    Example: job_vacancy BG 2019-Q1..2025-Q4, 28 observations, 0 missing periods, 12 provisional
    """
    lines = []
    for (name, country), group in indicators.groupby(["indicator", "country_code"], sort=True):
        group = group.sort_values("period_start")
        first = group.iloc[0]
        last = group.iloc[-1]
        expected = _periods_between(first["period_start"], last["period_start"], first["frequency"])
        provisional = int((group["obs_status"] == "p").sum())
        lines.append(
            {
                "indicator": name,
                "country_code": country,
                "frequency": first["frequency"],
                "first_period": first["period"],
                "last_period": last["period"],
                "observations": len(group),
                "missing_periods": expected - len(group),
                "provisional_values": provisional,
                "source_last_updated": first["source_last_updated"],
            }
        )
    return lines


def _periods_between(first_start, last_start, frequency: str) -> int:
    """How many periods from first to last, both included. 2019-01..2019-03 monthly -> 3."""
    months = (last_start.year - first_start.year) * 12 + (last_start.month - first_start.month)
    if frequency == "monthly":
        return months + 1
    if frequency == "quarterly":
        return months // 3 + 1
    return last_start.year - first_start.year + 1
