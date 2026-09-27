"""The queries behind each API endpoint (D-44, D-77).

Spring analogy: the @Service layer between the @RestControllers (api/routers) and the
repository (CuratedStore). Controllers stay thin: they read the query parameters and call one
function here. Validation errors are raised as domain errors and turned into HTTP codes in api/errors.py:
    NotFoundError       -> 404   unknown objective / country / indicator / segment value
    InvalidFilterError  -> 400   e.g. year_from after year_to, badly written segment filter
    DataNotBuiltError   -> 503   nothing built yet
"""

from __future__ import annotations

import math
from datetime import date, datetime

import duckdb
import numpy as np
import pandas as pd

from retention.config import Settings
from retention.domain.errors import InvalidFilterError, NotFoundError
from retention.repository.curated_store import CuratedStore
from retention.service.association import OBJECTIVE_LABELS, VIEWS, view_values
from retention.service.metrics import compute_retention_cohorts

COMPANY = "ALL"
COUNTRY_NAMES = {
    "ALL": "Company (all countries)",
    "GR": "Greece",
    "RO": "Romania",
    "PL": "Poland",
    "IT": "Italy",
    "IE": "Ireland",
    "BG": "Bulgaria",
}
SEGMENT_DIMENSIONS = ["employment_type", "career_level", "business_unit", "job_family"]
HIRE_OBJECTIVES = ["NEW_HIRE_6M", "SENIOR_HIRE_12M"]
TURNOVER_OBJECTIVE = "REGRETTED_TURNOVER_12M"

# Human-readable notes for the Trust view (from D-25, D-26, D-59, Round 6 side finding).
SOURCE_NOTES = {
    "unemployment": "Seasonally adjusted, all ages, both sexes.",
    "inflation": (
        "prc_hicp_manr was discontinued in 2026 (successor prc_hicp_minr, ECOICOP v2, dimension coicop18); "
        "it fully covers 2019-2025 (D-25)."
    ),
    "job_vacancy": (
        "Not seasonally adjusted; dataset labelled 2001-2025 (likely frozen after a classification change); "
        "some recent values are provisional (p)."
    ),
    "gdp_growth": (
        "Annual; carried forward with its own year and age, never shown as a quarterly value (D-31). "
        "Ireland kept but excluded from GDP tests: multinational accounting distorts Irish GDP (D-59)."
    ),
}
LAG_WORDING = (
    "Publication lags are conservative fixed-lag approximations based on observed source availability, "
    "not exact historical release dates; the APIs return today's revised values (D-58)."
)


# ---------------------------------------------------------------------------------------------
# JSON helpers and validation
# ---------------------------------------------------------------------------------------------


def records(table: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of JSON-safe dicts: NaN/NaT -> None, dates -> "YYYY-MM-DD", numpy -> Python."""
    result = []
    for row in table.to_dict("records"):
        clean = {}
        for key, value in row.items():
            clean[key] = _json_value(value)
        result.append(clean)
    return result


def _json_value(value):
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def objective_meta(store: CuratedStore, settings: Settings, objective: str) -> dict:
    """Target, direction, role and label of one objective; 404 if unknown."""
    objectives = store.table("canonical", "objectives")
    match = objectives[objectives["objective_id"] == objective]
    if match.empty:
        known = ", ".join(objectives["objective_id"])
        raise NotFoundError(f"unknown objective '{objective}' (known: {known})")
    row = records(match)[0]
    analysis = settings.analysis.objectives[objective]
    return {
        "objective_id": objective,
        "name": row["objective_name"],
        "direction": row["direction"],
        "target": row["target_value"],
        "scope": row["scope"],
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"],
        "role": analysis.role,
        "analysis_grain": analysis.grain,
        "label": OBJECTIVE_LABELS[objective],
    }


def check_country(settings: Settings, country: str, allow_company: bool = True) -> None:
    allowed = list(settings.countries)
    if allow_company:
        allowed = [COMPANY] + allowed
    if country not in allowed:
        raise NotFoundError(f"unknown country '{country}' (known: {', '.join(allowed)})")


def check_years(year_from: int | None, year_to: int | None) -> None:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise InvalidFilterError(f"year_from ({year_from}) is after year_to ({year_to})")


def parse_segment(segment: str | None) -> tuple[str, str] | None:
    """ "employment_type:Fixed Term" -> ("employment_type", "Fixed Term"). None stays None."""
    if segment is None or segment == "":
        return None
    if ":" not in segment:
        raise InvalidFilterError(
            f"segment must look like 'dimension:value', e.g. 'employment_type:Fixed Term' (got '{segment}')"
        )
    dimension, value = segment.split(":", 1)
    if dimension not in SEGMENT_DIMENSIONS:
        raise InvalidFilterError(
            f"unknown segment dimension '{dimension}' (allowed: {', '.join(SEGMENT_DIMENSIONS)})"
        )
    return dimension, value


def keep_rows(table: pd.DataFrame, keep: list[bool]) -> pd.DataFrame:
    """Keep the rows marked True. (table[keep] with an EMPTY list would select zero COLUMNS.)"""
    mask = pd.Series(keep, index=table.index, dtype=bool)
    return table[mask]


def _period_year(period: str) -> int | None:
    """ "2023-Q1" -> 2023, "2023" -> 2023, "2021-2025" (whole period) -> None."""
    if len(period) == 4:
        return int(period)
    if "-Q" in period:
        return int(period[:4])
    return None


def _in_years(year: int | None, year_from: int | None, year_to: int | None) -> bool:
    if year is None:
        return True  # the whole-period row is always shown
    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    return True


# ---------------------------------------------------------------------------------------------
# Health and filters
# ---------------------------------------------------------------------------------------------


def health(store: CuratedStore, settings: Settings) -> dict:
    """ok = data built and last run succeeded with no stale/unavailable source; else degraded / no_data."""
    summary = store.run_summary()
    built = store.is_built()
    build_record = store.document("analytical", "_build") if built else None

    problems = []
    source_states = {}
    if summary is not None:
        for source in summary["sources"]:
            source_states[source["indicator"]] = source["status"]
            if source["status"] in ("stale", "unavailable"):
                problems.append(f"{source['indicator']} is {source['status']}")
        if summary["outcome"] != "succeeded":
            problems.append(f"last run {summary['run_id']} failed: {summary.get('error')}")

    if not built:
        status = "no_data"
        message = "No curated data yet - run `retention run` first."
    elif problems:
        status = "degraded"
        message = "Data is available, but: " + "; ".join(problems)
    else:
        status = "ok"
        message = "Data built and all sources usable."

    return {
        "status": status,
        "message": message,
        "as_of_date": settings.as_of_date.isoformat(),
        "data_built_by_run": build_record["run_id"] if build_record else None,
        "data_built_at": build_record["built_at"] if build_record else None,
        "last_run": None
        if summary is None
        else {
            "run_id": summary["run_id"],
            "mode": summary["mode"],
            "outcome": summary["outcome"],
            "finished_at": summary["finished_at"],
        },
        "sources": source_states,
    }


def filters(store: CuratedStore, settings: Settings) -> dict:
    """Everything the dashboard needs to fill its dropdowns."""
    cohorts = store.table("analytical", "retention_cohorts")
    hires = store.table("analytical", "hire_outcomes")

    countries = []
    for code in [COMPANY] + list(settings.countries):
        countries.append({"code": code, "name": COUNTRY_NAMES.get(code, code)})

    objectives = []
    for objective_id in settings.analysis.objectives:
        objectives.append(objective_meta(store, settings, objective_id))

    segments = {}
    for dimension in SEGMENT_DIMENSIONS:
        segments[dimension] = sorted(hires[dimension].dropna().unique().tolist())

    years = sorted(cohorts[cohorts["grain"] == "year"]["period"].unique().tolist())
    quarters = sorted(cohorts[cohorts["grain"] == "quarter"]["period"].unique().tolist())

    indicators = []
    for name, indicator in settings.indicators.items():
        indicators.append(
            {
                "indicator": name,
                "lens": indicator.lens,
                "provider": indicator.provider,
                "frequency": indicator.frequency,
                "unit": indicator.unit,
            }
        )

    return {
        "countries": countries,
        "objectives": objectives,
        "segments": segments,
        "years": years,
        "quarters": quarters,
        "grains": ["quarter", "year", "period"],
        "variants": {
            "hire_objectives": ["primary", "with_unverified_exits"],
            "turnover": ["primary", "with_unverified_exits", "unknown_as_regretted"],
        },
        "indicators": indicators,
        "views": VIEWS,
    }


# ---------------------------------------------------------------------------------------------
# Retention objectives
# ---------------------------------------------------------------------------------------------


def cohorts(
    store: CuratedStore,
    settings: Settings,
    objective: str,
    country: str,
    grain: str,
    variant: str,
    segment: str | None,
    year_from: int | None,
    year_to: int | None,
) -> dict:
    """Hire-retention rows (NEW_HIRE_6M / SENIOR_HIRE_12M).

    Without a segment: the precomputed table. With a segment: recomputed on request from the
    hire-level table with exactly the same SQL and rules (D-77).
    """
    meta = objective_meta(store, settings, objective)
    if objective not in HIRE_OBJECTIVES:
        raise InvalidFilterError(f"{objective} is not a hire cohort objective; use /api/retention/turnover")
    check_country(settings, country)
    check_years(year_from, year_to)
    parsed_segment = parse_segment(segment)

    # 1. Get the table: precomputed, or recomputed for one segment.
    if parsed_segment is None:
        table = store.table("analytical", "retention_cohorts")
        computed = "precomputed by the pipeline"
    else:
        dimension, value = parsed_segment
        hires = store.table("analytical", "hire_outcomes")
        known_values = sorted(hires[dimension].unique().tolist())
        if value not in known_values:
            raise NotFoundError(f"unknown {dimension} value '{value}' (known: {', '.join(known_values)})")
        hires = hires[hires[dimension] == value]
        objectives = store.table("canonical", "objectives")
        con = duckdb.connect()
        table = compute_retention_cohorts(con, hires, objectives, settings)
        con.close()
        computed = f"computed on request for {dimension} = {value} (D-77)"

    # 2. Filter to the requested slice.
    scope = "company" if country == COMPANY else "country"
    table = table[
        (table["objective_id"] == objective)
        & (table["variant"] == variant)
        & (table["grain"] == grain)
        & (table["scope"] == scope)
        & (table["country_code"] == country)
    ]
    keep = []
    for period in table["period"]:
        keep.append(_in_years(_period_year(period), year_from, year_to))
    table = keep_rows(table, keep).sort_values("period")

    notes = [
        "Rates use mature hires only; hires whose window ends after the as-of date are counted as "
        "immature_hires (D-18).",
        "Status uses the 95% Wilson interval: met / not_met / inconclusive (D-75).",
        f"Rows with fewer than {settings.metrics.small_sample_below} people are flagged small_sample (D-78).",
    ]
    if grain == "quarter":
        notes.append("Quarter rows are a trend view: no status verdict (D-76).")
    if country == COMPANY:
        notes.append("Company rows include employees with an unknown country (D-08).")

    return {
        "objective": meta,
        "filters": {
            "country": country,
            "grain": grain,
            "variant": variant,
            "segment": segment,
            "year_from": year_from,
            "year_to": year_to,
        },
        "computed": computed,
        "rows": records(table),
        "notes": notes,
    }


def turnover(
    store: CuratedStore,
    settings: Settings,
    country: str,
    variant: str,
    year_from: int | None,
    year_to: int | None,
    year_end_only: bool,
) -> dict:
    """Monthly TTM regretted turnover; status only on December rows (D-37, D-76)."""
    meta = objective_meta(store, settings, TURNOVER_OBJECTIVE)
    check_country(settings, country)
    check_years(year_from, year_to)

    table = store.table("analytical", "regretted_turnover")
    table = table[(table["variant"] == variant) & (table["country_code"] == country)]
    if year_end_only:
        table = table[table["is_year_end"]]
    keep = []
    for month_end in table["month_end"]:
        keep.append(_in_years(month_end.year, year_from, year_to))
    table = keep_rows(table, keep).sort_values("month_end")

    return {
        "objective": meta,
        "filters": {
            "country": country,
            "variant": variant,
            "year_from": year_from,
            "year_to": year_to,
            "year_end_only": year_end_only,
        },
        "rows": records(table),
        "notes": [
            "Rate = regretted exits in the trailing 12 months / average of 13 month-end headcounts (D-20).",
            "Only confirmed TRUE regretted exits count; UNKNOWN is shown separately (D-12).",
            "Consecutive months share 11 of 12 months of data: status is given on December values only "
            "(D-37).",
            "CI treats average headcount as n: an approximation (D-33).",
        ],
    }


def sensitivity(store: CuratedStore, settings: Settings, objective: str) -> dict:
    """Primary vs sensitivity variants, company level, verdict rows only (D-10, D-12, D-22)."""
    meta = objective_meta(store, settings, objective)
    columns = ["variant", "period", "n", "rate", "ci_low", "ci_high", "status"]

    if objective == TURNOVER_OBJECTIVE:
        table = store.table("analytical", "regretted_turnover")
        table = table[(table["scope"] == "company") & table["is_year_end"]].copy()
        table["period"] = table["month_end"].map(lambda d: str(d.year))
        table["n"] = table["avg_headcount"]
        explanations = {
            "primary": "Confirmed TRUE regretted exits; unverified exits left out.",
            "with_unverified_exits": "Unverified 90-day exits added back to headcount and exits (D-22).",
            "unknown_as_regretted": "Worst case: every UNKNOWN regretted value counted as regretted (D-12).",
        }
    else:
        table = store.table("analytical", "retention_cohorts")
        table = table[
            (table["objective_id"] == objective)
            & (table["scope"] == "company")
            & (table["grain"].isin(["year", "period"]))
        ]
        explanations = {
            "primary": "Unverified exits quarantined (left out).",
            "with_unverified_exits": "Unverified exits treated as valid exits (D-10, D-57).",
        }

    # Years first, then the whole period ("2021-2025"), each with primary before the sensitivity variants.
    table = table[columns].copy()
    table["is_whole_period"] = table["period"].str.len() > 4
    table["variant_order"] = table["variant"].map(lambda v: 0 if v == "primary" else 1)
    table = table.sort_values(["is_whole_period", "period", "variant_order", "variant"])
    rows = records(table[columns])

    # How many verdicts change between primary and each sensitivity variant?
    primary_status = {}
    for row in rows:
        if row["variant"] == "primary":
            primary_status[row["period"]] = row["status"]
    changed = []
    for row in rows:
        if row["variant"] != "primary" and row["status"] != primary_status.get(row["period"]):
            changed.append(f"{row['period']} ({row['variant']})")

    return {
        "objective": meta,
        "variants": explanations,
        "rows": rows,
        "verdict_changes": changed,
        "summary": "No verdict changes under any sensitivity variant."
        if not changed
        else "Verdict changes: " + ", ".join(changed),
    }


# ---------------------------------------------------------------------------------------------
# External indicators and association
# ---------------------------------------------------------------------------------------------


def indicators(
    store: CuratedStore,
    settings: Settings,
    country: str | None,
    indicator: str | None,
    year_from: int | None,
    year_to: int | None,
) -> dict:
    """Canonical indicator series, each value with its own period, frequency and status (D-31)."""
    check_years(year_from, year_to)
    table = store.table("canonical", "indicators")
    if country is not None:
        check_country(settings, country, allow_company=False)
        table = table[table["country_code"] == country]
    if indicator is not None:
        if indicator not in settings.indicators:
            raise NotFoundError(f"unknown indicator '{indicator}' (known: {', '.join(settings.indicators)})")
        table = table[table["indicator"] == indicator]
    keep = []
    for start in table["period_start"]:
        keep.append(_in_years(start.year, year_from, year_to))
    table = keep_rows(table, keep)

    columns = [
        "indicator", "lens", "provider", "country_code", "period", "frequency", "period_start",
        "period_end", "value", "unit", "obs_status", "obs_status_label",
    ]  # fmt: skip
    return {
        "filters": {"country": country, "indicator": indicator, "year_from": year_from, "year_to": year_to},
        "rows": records(table[columns].sort_values(["indicator", "country_code", "period_start"])),
        "notes": [LAG_WORDING],
    }


def association(store: CuratedStore, settings: Settings, objective: str | None) -> dict:
    """Association results: formal within-country tests first, then descriptive views."""
    table = store.table("analytical", "association_results")
    if objective is not None:
        objective_meta(store, settings, objective)  # 404 if unknown
        table = table[table["objective_id"] == objective]
    order = {"within_country": 0, "pooled": 1, "time_adjusted": 2}
    table = table.assign(view_order=table["view"].map(order))
    table = table.sort_values(["objective_id", "view_order", "indicator"]).drop(columns=["view_order"])
    return {
        "rows": records(table),
        "notes": [
            "Formal test: within-country Spearman, Holm-corrected over 4 tests per objective (D-54, D-55).",
            "Pooled and time-adjusted views are descriptive context only (D-54, D-79).",
            "Bootstrap intervals are exploratory: rows are not independent (D-56).",
            "These results are associative, not causal (D-63).",
            LAG_WORDING,
        ],
    }


def association_points(
    store: CuratedStore,
    settings: Settings,
    objective: str,
    indicator: str,
    view: str,
    analysis_set: str,
) -> dict:
    """Scatter points for one objective x indicator: raw values plus the values used by the view."""
    objective_meta(store, settings, objective)
    if indicator not in settings.indicators:
        raise NotFoundError(f"unknown indicator '{indicator}' (known: {', '.join(settings.indicators)})")
    if view not in VIEWS:
        raise InvalidFilterError(f"unknown view '{view}' (allowed: {', '.join(VIEWS)})")

    aligned = store.table("analytical", "aligned_observations")
    rows = aligned[
        (aligned["objective_id"] == objective)
        & (aligned["indicator"] == indicator)
        & (aligned["analysis_set"] == analysis_set)
    ].sort_values(["country_code", "anchor_date"])

    # The view's x/y are computed only on rows that enter the test (e.g. IE is out of GDP tests).
    used = rows[~rows["excluded_from_tests"]]
    x, y = view_values(
        list(used["value"]),
        list(used["outcome_rate"]),
        list(used["country_code"]),
        list(used["period"]),
        view,
    )
    rows = rows.copy()
    rows["view_x"] = None
    rows["view_y"] = None
    rows.loc[used.index, "view_x"] = x
    rows.loc[used.index, "view_y"] = y

    columns = [
        "country_code", "period", "anchor_date", "outcome_rate", "cohort_n", "value", "source_period",
        "source_frequency", "age_months", "obs_status", "excluded_from_tests", "exclusion_reason",
        "view_x", "view_y",
    ]  # fmt: skip
    return {
        "objective_id": objective,
        "indicator": indicator,
        "view": view,
        "analysis_set": analysis_set,
        "points": records(rows[columns]),
    }


# ---------------------------------------------------------------------------------------------
# Trust: quality and sources
# ---------------------------------------------------------------------------------------------


def quality(store: CuratedStore) -> dict:
    """Quality report, the flagged rows, and which run built each layer."""
    report = store.document("canonical", "quality_report")
    issues = store.table("canonical", "quality_issues")
    builds = {}
    for layer in ["source_shaped", "canonical", "analytical"]:
        record = store.document(layer, "_build")
        builds[layer] = {
            "run_id": record["run_id"],
            "built_at": record["built_at"],
            "tables": record["tables"],
        }
    return {
        "report": report,
        "issues": records(issues),
        "builds": builds,
        "principle": (
            "Uncertain data is preserved, flagged and quarantined from the primary KPI. "
            "It is never deleted or imputed. Its impact is shown through sensitivity analysis."
        ),
    }


def sources(store: CuratedStore, settings: Settings) -> dict:
    """Provider, dataset, licence, cadence, freshness and coverage per source (brief: source attribution)."""
    summary = store.run_summary() or {"sources": []}
    status_by_source = {}
    for source in summary["sources"]:
        status_by_source[source["indicator"]] = source

    report = store.document("canonical", "quality_report")
    coverage_by_indicator = {}
    for line in report["indicators"]["coverage"]:
        coverage_by_indicator.setdefault(line["indicator"], []).append(line)

    rows = []
    for name, indicator in settings.indicators.items():
        terms = settings.provider_terms[indicator.provider]
        status = status_by_source.get(name, {})
        coverage = coverage_by_indicator.get(name, [])
        first_periods = []
        last_periods = []
        for line in coverage:
            first_periods.append(line["first_period"])
            last_periods.append(line["last_period"])
        if indicator.provider == "eurostat":
            page = f"https://ec.europa.eu/eurostat/databrowser/view/{indicator.dataset}/default/table"
        else:
            page = f"https://data.worldbank.org/indicator/{indicator.dataset}"
        rows.append(
            {
                "indicator": name,
                "lens": indicator.lens,
                "provider": terms.name,
                "dataset": indicator.dataset,
                "dataset_page": page,
                "frequency": indicator.frequency,
                "unit": indicator.unit,
                "filters": indicator.filters,
                "publication_lag_months": settings.publication_lag_months[indicator.frequency],
                "licence": terms.licence,
                "terms_url": terms.terms_url,
                "attribution": terms.attribution,
                "status": status.get("status"),
                "snapshot": status.get("snapshot"),
                "fetched_at": status.get("loaded_at"),
                "latest_period": status.get("source_period"),
                "provider_last_updated": coverage[0]["source_last_updated"] if coverage else None,
                "coverage_first_period": min(first_periods) if first_periods else None,
                "coverage_last_period": max(last_periods) if last_periods else None,
                "note": SOURCE_NOTES.get(name, ""),
            }
        )

    hr_terms = settings.provider_terms["hr"]
    hr_status = status_by_source.get("hr_pack", {})
    rows.append(
        {
            "indicator": "hr_pack",
            "lens": "workforce",
            "provider": hr_terms.name,
            "dataset": "employee_lifecycle_events.csv, retention_objectives.csv",
            "dataset_page": "",
            "frequency": "snapshot",
            "unit": "",
            "filters": {},
            "publication_lag_months": None,
            "licence": hr_terms.licence,
            "terms_url": hr_terms.terms_url,
            "attribution": hr_terms.attribution,
            "status": hr_status.get("status"),
            "snapshot": hr_status.get("snapshot"),
            "fetched_at": None,
            "latest_period": hr_status.get("source_period"),
            "provider_last_updated": None,
            "coverage_first_period": None,
            "coverage_last_period": None,
            "note": "Checked against the SHA-256 checksums in the pack's manifest on every run (D-65).",
        }
    )
    return {"sources": rows, "notes": [LAG_WORDING]}
