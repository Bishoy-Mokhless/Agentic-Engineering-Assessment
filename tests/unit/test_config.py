"""Settings load and match the recorded decisions."""

import csv

from retention.config import load_settings


def test_settings_load_and_validate():
    settings = load_settings()
    assert settings.countries == ["GR", "RO", "PL", "IT", "IE", "BG"]
    assert str(settings.as_of_date) == "2025-12-31"


def test_publication_lags_match_d29():
    lags = load_settings().publication_lag_months
    assert lags == {"monthly": 2, "quarterly": 3, "annual": 7}


def test_every_indicator_frequency_has_a_lag():
    settings = load_settings()
    for name, indicator in settings.indicators.items():
        assert indicator.frequency in settings.publication_lag_months, name


def test_two_providers_and_at_least_three_indicators():
    """Brief minimum: >= 2 providers, >= 3 indicators (D-24..D-27)."""
    indicators = load_settings().indicators.values()
    assert len({i.provider for i in indicators}) >= 2
    assert len(list(indicators)) >= 3


def test_formal_tests_are_within_country_only_four_per_objective():
    """D-54/D-55: pooled is descriptive; each objective's Holm family = 4 indicators x within-country."""
    settings = load_settings()
    analysis = settings.analysis
    assert analysis.formal_view == "within_country"
    assert "within_country" not in analysis.descriptive_views
    assert set(analysis.objectives) == {"NEW_HIRE_6M", "SENIOR_HIRE_12M", "REGRETTED_TURNOVER_12M"}
    assert len(settings.indicators) == 4  # one formal test per indicator -> Holm family of 4


def test_only_new_hire_6m_is_primary():
    """D-35: one primary analysis; the other two are secondary sensitivity analyses."""
    objectives = load_settings().analysis.objectives
    assert [name for name, o in objectives.items() if o.role == "primary"] == ["NEW_HIRE_6M"]


def test_country_mapping_covers_every_provider_and_country():
    settings = load_settings()
    with open(settings.paths.mappings / "country_codes.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for source in ("hr", "eurostat", "worldbank"):
        canonical = {r["canonical_code"] for r in rows if r["source"] == source}
        assert canonical == set(settings.countries), source


def test_senior_levels_are_a_setting_d94():
    # D-14 assumption, now a setting (D-94): which career levels count as "senior".
    assert load_settings().metrics.senior_levels == ["Senior Leader"]


# --- F-15 (D-99): a typo or an impossible value in settings.yaml stops at startup ---


def write_settings(tmp_path, change):
    import yaml

    from retention.config import DEFAULT_SETTINGS_FILE

    data = yaml.safe_load(DEFAULT_SETTINGS_FILE.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_misspelled_setting_is_rejected(tmp_path):
    import pytest
    from pydantic import ValidationError

    def typo(data):  # "exclude_from_analysis" misspelled: the Ireland GDP exclusion (D-59) would be lost
        data["indicators"]["gdp_growth"]["exclude_from_analyis"] = data["indicators"]["gdp_growth"].pop(
            "exclude_from_analysis"
        )

    with pytest.raises(ValidationError, match="exclude_from_analyis"):
        load_settings(write_settings(tmp_path, typo))


def test_impossible_values_are_rejected(tmp_path):
    import pytest
    from pydantic import ValidationError

    def negative_retries(data):
        data["http"]["retries"] = -5

    def alpha_above_one(data):
        data["analysis"]["alpha"] = 5

    for change in (negative_retries, alpha_above_one):
        with pytest.raises(ValidationError):
            load_settings(write_settings(tmp_path, change))
