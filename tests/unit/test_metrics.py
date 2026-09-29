"""Metric rules (D-16..D-22, D-75..D-78): tiny hand-made employee tables run through the real SQL files."""

from datetime import date

import duckdb
import pandas as pd
import pytest

from retention.config import load_settings
from retention.domain.errors import CurationError
from retention.service.metrics import (
    check_senior_levels,
    compute_hire_outcomes,
    compute_regretted_turnover,
    compute_retention_cohorts,
)
from retention.service.stats import objective_status, wilson_interval

SETTINGS = load_settings()  # report_start 2021-01-01, as_of 2025-12-31
OBJECTIVES = pd.DataFrame(
    [
        {"objective_id": "NEW_HIRE_6M", "direction": "at_least", "target_value": 0.86},
        {"objective_id": "SENIOR_HIRE_12M", "direction": "at_least", "target_value": 0.90},
        {"objective_id": "REGRETTED_TURNOVER_12M", "direction": "at_most", "target_value": 0.075},
    ]
)


def employee(employee_id, hire, term=None, **changes):
    """One canonical employee row. Dates as 'YYYY-MM-DD' text for readability."""
    row = {
        "employee_id": employee_id,
        "metric_status": "INCLUDED",
        "country_code": "GR",
        "business_unit": "Sales",
        "job_family": "Field Sales",
        "career_level": "Manager",
        "employment_type": "Permanent",
        "hire_date": date.fromisoformat(hire),
        "termination_date": date.fromisoformat(term) if term else None,
        "termination_type": "Voluntary" if term else "NOT_APPLICABLE",
        "regretted_exit": "FALSE" if term else "NOT_APPLICABLE",
    }
    row.update(changes)
    return row


def connect(*rows):
    con = duckdb.connect()
    con.register("employees", pd.DataFrame(list(rows)))
    return con


def outcomes(*rows):
    """hire_outcomes as {(objective, employee_id): row}."""
    table = compute_hire_outcomes(connect(*rows), SETTINGS)
    result = {}
    for row in table.to_dict("records"):
        result[(row["objective_id"], row["employee_id"])] = row
    return result


# --- stats (D-33, D-75) ----------------------------------------------------------------------


def test_wilson_interval_known_values():
    low, high = wilson_interval(12, 16)
    assert round(low, 3) == 0.505 and round(high, 3) == 0.898
    low, high = wilson_interval(1, 1)
    assert round(low, 3) == 0.207 and high == 1.0  # never above 100%
    assert wilson_interval(0, 0) is None


def test_status_needs_whole_interval_on_one_side():
    assert objective_status(0.86, 0.95, 0.86, "at_least") == "met"  # boundary counts as met
    assert objective_status(0.70, 0.859, 0.86, "at_least") == "not_met"
    assert objective_status(0.50, 0.90, 0.86, "at_least") == "inconclusive"
    assert objective_status(0.02, 0.075, 0.075, "at_most") == "met"
    assert objective_status(0.08, 0.10, 0.075, "at_most") == "not_met"
    with pytest.raises(ValueError, match="unknown objective direction"):
        objective_status(0.1, 0.2, 0.1, "sideways")


# --- hire outcomes (D-16, D-17, D-18, D-14) --------------------------------------------------


def test_observation_date_uses_calendar_months_with_month_end_clamp():
    result = outcomes(employee("A", "2021-08-31"))
    assert result[("NEW_HIRE_6M", "A")]["observation_date"] == date(2022, 2, 28)


def test_leaving_on_the_observation_date_is_not_retained_one_day_later_is():
    result = outcomes(
        employee("ON_DAY", "2023-01-15", "2023-07-15"),
        employee("DAY_AFTER", "2023-01-15", "2023-07-16"),
    )
    assert result[("NEW_HIRE_6M", "ON_DAY")]["outcome"] == "not_retained"
    assert result[("NEW_HIRE_6M", "ON_DAY")]["exit_type_in_window"] == "Voluntary"
    assert result[("NEW_HIRE_6M", "DAY_AFTER")]["outcome"] == "retained"
    assert result[("NEW_HIRE_6M", "DAY_AFTER")]["exit_type_in_window"] is None


def test_window_ending_after_as_of_is_immature_even_if_already_left():
    result = outcomes(employee("RECENT", "2025-07-01", "2025-08-01"))  # observation 2026-01-01
    assert result[("NEW_HIRE_6M", "RECENT")]["outcome"] == "immature"


def test_senior_objective_only_for_senior_leaders_and_hires_before_2021_are_out():
    result = outcomes(
        employee("MGR", "2022-03-01"),
        employee("SL", "2022-03-01", career_level="Senior Leader"),
        employee("OLD", "2020-06-01", career_level="Senior Leader"),
    )
    assert ("SENIOR_HIRE_12M", "SL") in result
    assert ("SENIOR_HIRE_12M", "MGR") not in result
    assert ("NEW_HIRE_6M", "OLD") not in result  # 2020 hires are history only (D-23)


def test_senior_levels_come_from_the_settings_d94():
    # If the business decides Managers are senior too, only settings.yaml changes.
    settings = SETTINGS.model_copy(deep=True)
    settings.metrics.senior_levels = ["Senior Leader", "Manager"]
    table = compute_hire_outcomes(
        connect(
            employee("MGR", "2022-03-01"), employee("IC", "2022-03-01", career_level="Individual Contributor")
        ),
        settings,
    )
    senior = set(table[table["objective_id"] == "SENIOR_HIRE_12M"]["employee_id"])
    assert senior == {"MGR"}


def test_a_senior_level_that_does_not_exist_stops_the_run():
    known = ["Individual Contributor", "Manager", "Senior Leader"]
    check_senior_levels(["Senior Leader"], known)  # fine
    with pytest.raises(CurationError, match="Senior Leaders"):
        check_senior_levels(["Senior Leaders"], known)  # a typo would silently give 0 senior hires
    with pytest.raises(CurationError, match="at least one"):
        check_senior_levels([], known)


def test_excluded_rows_never_appear_and_quarantined_rows_keep_their_status():
    result = outcomes(
        employee("BAD", "2022-01-01", metric_status="EXCLUDED"),
        employee("Q", "2022-01-01", "2022-04-01", metric_status="QUARANTINED", termination_type="Unknown"),
    )
    assert ("NEW_HIRE_6M", "BAD") not in result
    assert result[("NEW_HIRE_6M", "Q")]["metric_status"] == "QUARANTINED"


# --- cohorts (D-19, D-76, D-77, D-78, D-08, D-10) --------------------------------------------


def cohorts(*rows):
    con = connect(*rows)
    return compute_retention_cohorts(con, compute_hire_outcomes(con, SETTINGS), OBJECTIVES, SETTINGS)


def pick(table, **where):
    mask = pd.Series(True, index=table.index)
    for column, value in where.items():
        mask = mask & (table[column] == value)
    assert mask.sum() == 1, where
    return table[mask].iloc[0]


def test_company_includes_unknown_country_but_country_view_does_not():
    table = cohorts(
        employee("A", "2022-02-01"),
        employee("B", "2022-02-01", country_code="Unknown"),
    )
    company = pick(table, objective_id="NEW_HIRE_6M", variant="primary", grain="year", scope="company")
    assert company["n"] == 2
    assert "Unknown" not in set(table["country_code"])


def test_quarter_rows_have_no_verdict_but_year_and_period_rows_do():
    table = cohorts(employee("A", "2022-02-01"))
    quarter = pick(table, objective_id="NEW_HIRE_6M", variant="primary", grain="quarter", scope="company")
    year = pick(table, objective_id="NEW_HIRE_6M", variant="primary", grain="year", scope="company")
    assert quarter["period"] == "2022-Q1" and quarter["status"] is None
    assert year["period"] == "2022" and year["status"] == "inconclusive"  # 1/1: CI far too wide
    assert year["small_sample"]  # n = 1 < 10


def test_sensitivity_variant_adds_unverified_exits_as_not_retained():
    table = cohorts(
        employee("A", "2022-02-01"),
        employee("Q", "2022-02-01", "2022-05-02", metric_status="QUARANTINED", termination_type="Unknown"),
    )
    primary = pick(table, objective_id="NEW_HIRE_6M", variant="primary", grain="period", scope="company")
    sensitivity = pick(
        table, objective_id="NEW_HIRE_6M", variant="with_unverified_exits", grain="period", scope="company"
    )
    assert (primary["n"], primary["retained"]) == (1, 1)
    assert (sensitivity["n"], sensitivity["retained"]) == (2, 1)
    assert sensitivity["exits_unknown_type"] == 1


def test_cohort_with_no_mature_hires_has_no_rate():
    table = cohorts(employee("SL", "2025-03-01", career_level="Senior Leader"))  # 12m window ends 2026
    row = pick(table, objective_id="SENIOR_HIRE_12M", variant="primary", grain="year", scope="company")
    assert row["n"] == 0 and row["immature_hires"] == 1
    assert pd.isna(row["rate"]) and row["status"] is None


# --- regretted turnover (D-20, D-21, D-22, D-12, D-37) ---------------------------------------


def turnover(*rows):
    return compute_regretted_turnover(connect(*rows), OBJECTIVES, SETTINGS)


def december(table, year, variant="primary"):
    return pick(table, variant=variant, scope="company", month_end=date(year, 12, 31))


def test_ttm_window_is_exactly_the_12_months_ending_at_the_month_end():
    # Exit on 2023-12-31 belongs to the 2023 window, NOT to the 2024 one; exit on 2024-12-31 belongs to 2024.
    table = turnover(
        employee("STAY", "2020-01-01"),
        employee("X1", "2020-01-01", "2023-12-31", regretted_exit="TRUE"),
        employee("X2", "2020-01-01", "2024-12-31", regretted_exit="TRUE"),
    )
    assert december(table, 2023)["regretted_exits"] == 1
    assert december(table, 2024)["regretted_exits"] == 1


def test_average_headcount_uses_13_month_ends_and_excludes_leavers_on_their_exit_day():
    # STAY: employed all year (13/13). NEW: hired 2024-06-15 -> counted at Jun..Dec 2024 month-ends (7/13).
    # LEFT: leaves 2024-01-31 -> counted only at 2023-12-31 (termination date itself is not counted, D-20).
    table = turnover(
        employee("STAY", "2020-01-01"),
        employee("NEW", "2024-06-15"),
        employee("LEFT", "2020-01-01", "2024-01-31"),
    )
    row = december(table, 2024)
    assert row["headcount_points"] == 13
    assert row["avg_headcount"] == pytest.approx((13 + 7 + 1) / 13)


def test_only_confirmed_true_is_regretted_unless_worst_case_variant():
    table = turnover(
        employee("STAY", "2020-01-01"),
        employee("U", "2020-01-01", "2024-05-01", regretted_exit="UNKNOWN"),
        employee("F", "2020-01-01", "2024-06-01", regretted_exit="FALSE"),
    )
    assert december(table, 2024)["regretted_exits"] == 0
    assert december(table, 2024)["unknown_regretted_exits"] == 1
    assert december(table, 2024, "unknown_as_regretted")["regretted_exits"] == 1


def test_quarantined_employees_only_in_the_sensitivity_headcount():
    table = turnover(
        employee("STAY", "2020-01-01"),
        employee("Q", "2020-01-01", metric_status="QUARANTINED"),
    )
    assert december(table, 2024)["avg_headcount"] == 1
    assert december(table, 2024, "with_unverified_exits")["avg_headcount"] == 2


def test_turnover_verdicts_only_on_december_rows():
    table = turnover(employee("STAY", "2020-01-01"))
    june = pick(table, variant="primary", scope="company", month_end=date(2024, 6, 30))
    assert june["status"] is None
    assert december(table, 2024)["status"] in ("met", "inconclusive")
    assert table["month_end"].min() == date(2021, 1, 31) and table["month_end"].max() == date(2025, 12, 31)
