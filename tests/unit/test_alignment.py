"""As-of join: no future information, lags, frequency integrity (D-28..D-31, D-38, D-59)."""

from datetime import date

import duckdb
import pandas as pd
import pytest

from retention.config import load_settings
from retention.domain import schemas
from retention.domain.errors import ContractError
from retention.domain.periods import period_bounds
from retention.service.alignment import align_indicators, build_analysis_units, quarter_start

SETTINGS = load_settings()  # lags: monthly 2, quarterly 3, annual 7


def indicator_row(indicator, country, period, frequency, value):
    start, end = period_bounds(period, frequency)
    return {
        "indicator": indicator,
        "country_code": country,
        "period": period,
        "frequency": frequency,
        "period_start": start,
        "period_end": end,
        "value": value,
        "lens": "test",
        "unit": "%",
        "obs_status": None,
        "source_snapshot": "test",
    }


def unit(anchor, country="GR", objective="NEW_HIRE_6M"):
    return {
        "objective_id": objective,
        "analysis_set": "formal",
        "grain": "quarter",
        "country_code": country,
        "period": "P",
        "anchor_date": anchor,
        "outcome_rate": 0.9,
        "cohort_n": 10.0,
    }


def align(indicators, units):
    con = duckdb.connect()
    con.register("indicators", pd.DataFrame(indicators))
    return align_indicators(con, pd.DataFrame(units), SETTINGS)


def value_for(aligned, indicator):
    return aligned[aligned["indicator"] == indicator].iloc[0]


MONTHLY = [
    indicator_row("unemployment", "GR", "2022-09", "monthly", 12.0),
    indicator_row("unemployment", "GR", "2022-10", "monthly", 11.8),  # usable from 2022-12-31
    indicator_row("unemployment", "GR", "2022-11", "monthly", 11.6),  # usable from 2023-01-31
]


def test_monthly_value_is_latest_month_already_published():
    row = value_for(align(MONTHLY, [unit(date(2023, 1, 1))]), "unemployment")
    assert row["value"] == 11.8 and row["source_period"] == "2022-10"
    assert row["available_from"] == date(2022, 12, 31)
    assert row["age_months"] == 3


def test_value_published_exactly_on_the_as_of_date_is_usable_one_day_earlier_is_not():
    on_the_day = value_for(align(MONTHLY, [unit(date(2022, 12, 31))]), "unemployment")
    day_before = value_for(align(MONTHLY, [unit(date(2022, 12, 30))]), "unemployment")
    assert on_the_day["source_period"] == "2022-10"
    assert day_before["source_period"] == "2022-09"


def test_quarterly_value_uses_three_month_lag():
    rows = [
        indicator_row("job_vacancy", "GR", "2022-Q3", "quarterly", 1.1),  # usable 2022-12-31
        indicator_row("job_vacancy", "GR", "2022-Q4", "quarterly", 0.9),  # usable 2023-03-31
    ]
    row = value_for(align(rows, [unit(date(2023, 1, 1))]), "job_vacancy")
    assert row["source_period"] == "2022-Q3" and row["age_months"] == 4


def test_annual_value_is_carried_forward_with_its_own_period_frequency_and_age():
    rows = [
        indicator_row("gdp_growth", "GR", "2021", "annual", 8.7),  # usable 2022-07-31
        indicator_row("gdp_growth", "GR", "2022", "annual", 5.5),  # usable 2023-07-31
    ]
    aligned = align(rows, [unit(date(2023, 1, 1)), unit(date(2023, 4, 1))])
    both = aligned[aligned["indicator"] == "gdp_growth"]
    assert list(both["source_period"]) == ["2021", "2021"]  # same annual value for two quarters ...
    assert list(both["source_frequency"]) == ["annual", "annual"]  # ... but never presented as quarterly
    assert list(both["age_months"]) == [13, 16]  # and it visibly ages


def test_no_published_value_yet_is_kept_but_excluded_from_tests():
    row = value_for(align(MONTHLY, [unit(date(2022, 1, 1))]), "unemployment")
    assert pd.isna(row["value"])
    assert row["excluded_from_tests"] and "no published value" in row["exclusion_reason"]


def test_ireland_gdp_is_kept_but_excluded_from_gdp_tests_only():
    rows = [
        indicator_row("gdp_growth", "IE", "2021", "annual", 15.0),
        indicator_row("unemployment", "IE", "2022-10", "monthly", 4.5),
    ]
    aligned = align(rows, [unit(date(2023, 1, 1), country="IE")])
    gdp = value_for(aligned, "gdp_growth")
    assert gdp["value"] == 15.0 and gdp["excluded_from_tests"]
    assert "D-59" in gdp["exclusion_reason"]
    assert not value_for(aligned, "unemployment")["excluded_from_tests"]


def test_contract_rejects_future_information():
    aligned = align(MONTHLY, [unit(date(2023, 1, 1))])
    aligned.loc[aligned["indicator"] == "unemployment", "available_from"] = date(2023, 6, 30)
    with pytest.raises(ContractError, match="no future information"):
        schemas.check_contract(schemas.ALIGNED_OBSERVATIONS, aligned, "aligned")


def test_analysis_units_anchors():
    assert quarter_start("2023-Q3") == date(2023, 7, 1)
    cohorts = pd.DataFrame(
        [
            {"objective_id": "NEW_HIRE_6M", "variant": "primary", "scope": "country", "grain": "quarter",
             "country_code": "GR", "period": "2023-Q2", "n": 10, "rate": 0.9},
            {"objective_id": "SENIOR_HIRE_12M", "variant": "primary", "scope": "country", "grain": "year",
             "country_code": "GR", "period": "2023", "n": 10, "rate": 0.8},
            {"objective_id": "SENIOR_HIRE_12M", "variant": "primary", "scope": "country", "grain": "quarter",
             "country_code": "GR", "period": "2023-Q2", "n": 2, "rate": 0.5},
            {"objective_id": "NEW_HIRE_6M", "variant": "primary", "scope": "company", "grain": "quarter",
             "country_code": "ALL", "period": "2023-Q2", "n": 90, "rate": 0.9},
        ]
    )  # fmt: skip
    turnover = pd.DataFrame(
        [{"variant": "primary", "scope": "country", "country_code": "GR", "is_year_end": True,
          "month_end": date(2024, 12, 31), "rate": 0.04, "avg_headcount": 150.0}]
    )  # fmt: skip
    units = build_analysis_units(cohorts, turnover)
    by_key = {(u["objective_id"], u["grain"]): u for u in units.to_dict("records")}
    assert by_key[("NEW_HIRE_6M", "quarter")]["anchor_date"] == date(2023, 4, 1)  # D-28
    assert by_key[("SENIOR_HIRE_12M", "year")]["anchor_date"] == date(2023, 1, 1)  # D-36
    assert by_key[("SENIOR_HIRE_12M", "quarter")]["analysis_set"] == "descriptive"
    assert by_key[("REGRETTED_TURNOVER_12M", "year_end_ttm")]["anchor_date"] == date(2024, 1, 1)  # D-38
    assert "ALL" not in set(units["country_code"])  # company rows are not analysed
