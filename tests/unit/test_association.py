"""Association rules: demeaning, Spearman, Holm, bootstrap, wording (D-54..D-56, D-63, D-79, D-80)."""

import math
from datetime import date

import pandas as pd
import pytest

from retention.config import load_settings
from retention.service.association import (
    bootstrap_interval,
    demean,
    holm_adjust,
    run_association,
    spearman_rho,
    view_values,
)


def test_demean_removes_each_group_average():
    assert demean([1, 3, 10, 14], ["A", "A", "B", "B"]) == [-1, 1, -2, 2]


def test_spearman_uses_ranks_handles_ties_and_constants():
    assert spearman_rho([1, 2, 3, 4], [10, 20, 30, 1000]) == pytest.approx(1.0)  # outlier does not matter
    assert spearman_rho([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert -1 <= spearman_rho([1, 1, 2, 2], [1, 2, 3, 4]) <= 1  # ties get average ranks
    assert math.isnan(spearman_rho([1, 1, 1], [1, 2, 3]))  # no variation -> undefined, not 0


def test_holm_step_down_example():
    assert holm_adjust([0.01, 0.04, 0.03, 0.20]) == pytest.approx([0.04, 0.09, 0.09, 0.20])
    assert holm_adjust([0.5, 0.6]) == pytest.approx([1.0, 1.0])  # capped at 1


def test_within_country_view_removes_between_country_differences():
    # Country B has higher indicator AND higher retention (a "countries differ" effect),
    # but inside each country the indicator moves OPPOSITE to retention.
    x = [1, 2, 3, 11, 12, 13]
    y = [0.53, 0.52, 0.51, 0.93, 0.92, 0.91]
    countries = ["A", "A", "A", "B", "B", "B"]
    periods = ["1", "2", "3", "1", "2", "3"]
    pooled_x, pooled_y = view_values(x, y, countries, periods, "pooled")
    within_x, within_y = view_values(x, y, countries, periods, "within_country")
    assert spearman_rho(pooled_x, pooled_y) > 0.4
    assert spearman_rho(within_x, within_y) == pytest.approx(-1.0)
    with pytest.raises(ValueError, match="unknown view"):
        view_values(x, y, countries, periods, "sideways")


def rows_for(countries=("GR", "RO", "PL"), periods=8, seed_shift=0.0):
    rows = []
    for c_index, country in enumerate(countries):
        for p in range(periods):
            anchor = date(2021 + p // 4, 1 + (p % 4) * 3, 1)
            rate = 0.8 + 0.01 * ((p * 7 + c_index) % 5) + seed_shift
            rows.append(
                {"country_code": country, "period": str(p), "anchor_date": anchor,
                 "value": float(p % 5 + c_index), "outcome_rate": rate}
            )  # fmt: skip
    return pd.DataFrame(rows)


def test_bootstrap_is_deterministic_with_the_same_seed():
    rows = rows_for()
    first = bootstrap_interval(rows, "within_country", 200, 20260831)
    second = bootstrap_interval(rows, "within_country", 200, 20260831)
    assert first == second
    assert first[0] <= first[1]


def aligned_table():
    """Synthetic aligned table: 3 objectives x 4 indicators, formal rows, IE excluded from GDP."""
    settings = load_settings()
    tables = []
    for objective in settings.analysis.objectives:
        for indicator in settings.indicators:
            rows = rows_for(countries=("GR", "RO", "PL", "IE"))
            rows["objective_id"] = objective
            rows["indicator"] = indicator
            rows["analysis_set"] = "formal"
            rows["excluded_from_tests"] = (indicator == "gdp_growth") & (rows["country_code"] == "IE")
            tables.append(rows)
    return pd.concat(tables, ignore_index=True)


def results():
    settings = load_settings()
    settings.analysis.bootstrap_iterations = 50  # keep the unit test fast
    return run_association(aligned_table(), settings)


def test_each_objective_has_one_holm_family_of_four_within_country_tests():
    table = results()
    formal = table[table["is_formal"]]
    assert set(formal["view"]) == {"within_country"}
    assert formal.groupby("objective_id").size().to_dict() == {
        "NEW_HIRE_6M": 4,
        "SENIOR_HIRE_12M": 4,
        "REGRETTED_TURNOVER_12M": 4,
    }
    assert (formal["holm_family_size"] == 4).all()
    assert table[~table["is_formal"]]["p_holm"].isna().all()  # descriptive views never get a Holm p


def test_excluded_countries_are_reported_with_the_result():
    table = results()
    gdp = table[(table["indicator"] == "gdp_growth") & table["is_formal"]].iloc[0]
    assert gdp["countries_excluded"] == "IE" and gdp["n_countries"] == 3
    assert "IE (D-59)" in gdp["caveat"]


def test_wording_follows_the_statistical_language_rules():
    table = results()
    text = " ".join(list(table["result"]) + list(table["caveat"])).lower()
    for banned in ["proves", "no relationship exists", " causes "]:
        assert banned not in text
    assert "associative, not causal" in text
    pooled = table[table["view"] == "pooled"].iloc[0]
    assert pooled["result"] == "Descriptive pooled context — not the primary formal test."
    labels = set(table["label"])
    assert "NEW_HIRE_6M — Primary association analysis" in labels
    assert "SENIOR_HIRE_12M — Secondary sensitivity analysis (low power)" in labels
