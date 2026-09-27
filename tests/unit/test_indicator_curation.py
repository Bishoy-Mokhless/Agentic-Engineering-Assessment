"""Indicator parsing and curation: JSON-stat decoding, periods, country mapping, status (D-08, D-31, D-71)."""

import json
from datetime import date
from pathlib import Path

import pytest

from retention.config import IndicatorSettings
from retention.domain.errors import CurationError
from retention.domain.periods import period_bounds
from retention.service.indicator_curation import SourceLineage, curate_indicator, provider_last_updated
from retention.service.indicator_parsing import flatten_eurostat, flatten_worldbank

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
LINEAGE = SourceLineage(
    snapshot="test/snapshot", loaded_at="2026-09-27T12:00:00+00:00", source_last_updated=None
)


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def indicator(provider="eurostat", frequency="quarterly"):
    return IndicatorSettings(
        provider=provider, dataset="test_ds", frequency=frequency, lens="test", unit="%", since="2019"
    )


# --- periods (D-31) ---------------------------------------------------------------------------


def test_period_bounds_for_each_frequency():
    assert period_bounds("2023-02", "monthly") == (date(2023, 2, 1), date(2023, 2, 28))
    assert period_bounds("2024-02", "monthly") == (date(2024, 2, 1), date(2024, 2, 29))  # leap year
    assert period_bounds("2023-Q1", "quarterly") == (date(2023, 1, 1), date(2023, 3, 31))
    assert period_bounds("2023-Q4", "quarterly") == (date(2023, 10, 1), date(2023, 12, 31))
    assert period_bounds("2021", "annual") == (date(2021, 1, 1), date(2021, 12, 31))


def test_bad_period_label_gives_clear_error():
    with pytest.raises(CurationError, match="'2023-Q5' is not a valid quarterly period"):
        period_bounds("2023-Q5", "quarterly")


# --- Eurostat JSON-stat -----------------------------------------------------------------------


def test_eurostat_positions_are_decoded_into_dimensions():
    table = flatten_eurostat(load("eurostat_small.json"))
    assert len(table) == 5  # 2 x 3 cells, one missing
    rows = {(r["geo"], r["time"]): r for r in table.to_dict("records")}
    assert rows[("EL", "2023-Q2")]["value"] == 1.6  # position 1
    assert rows[("BG", "2023-Q1")]["value"] == 0.9  # position 3 = geo 1, time 0
    assert ("BG", "2023-Q3") not in rows  # the missing cell is simply absent
    assert list(table.columns[:3]) == ["freq", "geo", "time"]  # provider's own dimensions kept


def test_eurostat_status_flag_and_label_are_kept():
    table = flatten_eurostat(load("eurostat_small.json"))
    bg_q1 = table[(table["geo"] == "BG") & (table["time"] == "2023-Q1")].iloc[0]
    assert bg_q1["status"] == "p" and bg_q1["status_label"] == "provisional"


def test_eurostat_values_as_list_are_supported():
    data = load("eurostat_small.json")
    data["value"] = [1.5, 1.6, 1.4, 0.9, 0.8, None]
    data["status"] = [None, None, None, "p", None, None]
    table = flatten_eurostat(data)
    assert len(table) == 5
    assert table[table["status"] == "p"].iloc[0]["geo"] == "BG"


def test_eurostat_canonical_rows_map_el_to_gr_and_keep_period_and_status():
    source = flatten_eurostat(load("eurostat_small.json"))
    result = curate_indicator(source, "job_vacancy", indicator(), {"EL": "GR", "BG": "BG"}, LINEAGE)
    rows = {(r["country_code"], r["period"]): r for r in result.rows.to_dict("records")}
    gr = rows[("GR", "2023-Q1")]
    assert gr["source_country_code"] == "EL"
    assert gr["period_start"] == date(2023, 1, 1) and gr["period_end"] == date(2023, 3, 31)
    assert gr["frequency"] == "quarterly" and gr["source_snapshot"] == "test/snapshot"
    assert rows[("BG", "2023-Q1")]["obs_status"] == "p"
    assert rows[("GR", "2023-Q1")]["obs_status"] is None


def test_unmapped_provider_country_stops_with_clear_message():
    source = flatten_eurostat(load("eurostat_small.json"))
    with pytest.raises(CurationError, match="country code 'BG' has no row"):
        curate_indicator(source, "job_vacancy", indicator(), {"EL": "GR"}, LINEAGE)


# --- World Bank -------------------------------------------------------------------------------


def test_worldbank_rows_keep_nulls_in_source_shaped_and_drop_them_in_canonical():
    data = load("worldbank_small.json")
    source = flatten_worldbank(data)
    assert len(source) == 3 and source["value"].isna().sum() == 1  # faithful: the null is still here

    result = curate_indicator(
        source, "gdp_growth", indicator("worldbank", "annual"), {"GRC": "GR", "BGR": "BG"}, LINEAGE
    )
    assert result.source_rows == 3 and result.missing_values_dropped == 1 and len(result.rows) == 2
    gr = result.rows[result.rows["country_code"] == "GR"].iloc[0]
    assert gr["period"] == "2021" and gr["frequency"] == "annual"  # annual stays annual (D-31)
    assert gr["period_end"] == date(2021, 12, 31)


def test_provider_last_updated():
    assert provider_last_updated("eurostat", load("eurostat_small.json")) == "2026-03-20T23:00:00+0100"
    assert provider_last_updated("worldbank", load("worldbank_small.json")) == "2026-07-13"
