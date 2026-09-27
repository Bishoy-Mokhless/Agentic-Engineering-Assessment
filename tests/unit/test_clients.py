"""Eurostat and World Bank clients: request building and response validation (no network)."""

import json

import pytest

from retention.client import eurostat, worldbank
from retention.client.http import SourceError
from retention.config import load_settings


def eurostat_payload(values: dict) -> bytes:
    """Minimal JSON-stat shaped like the real API: dims geo x time, time last."""
    return json.dumps(
        {
            "id": ["freq", "geo", "time"],
            "size": [1, 2, 3],
            "dimension": {
                "time": {"category": {"index": {"2025-10": 0, "2025-11": 1, "2025-12": 2}}},
            },
            "value": values,
        }
    ).encode()


def test_eurostat_request_uses_verified_codes_and_eurostat_geo():
    settings = load_settings()
    client = eurostat.EurostatClient(None, "https://x/", settings.http, ["EL", "RO"])
    url, params = client.build_request(settings.indicators["job_vacancy"])
    assert url == "https://x/jvs_q_nace2"
    assert ("indic_em", "JVR") in params  # D-26: JOBRATE returned no data
    assert ("geo", "EL") in params  # D-08: Eurostat uses EL for Greece
    assert ("sinceTimePeriod", "2019-Q1") in params


def test_eurostat_latest_period_is_last_period_with_a_value():
    # flat index = geo_pos * 3 + time_pos ; values only up to 2025-11
    summary = eurostat.summarize(json.loads(eurostat_payload({"0": 1.0, "1": 1.1, "4": 2.0})))
    assert summary.observation_count == 3
    assert summary.latest_period == "2025-11"


def test_eurostat_empty_response_is_an_error():
    with pytest.raises(SourceError, match="no observations"):
        eurostat.summarize(json.loads(eurostat_payload({})))


def test_eurostat_error_body_is_an_error():
    with pytest.raises(SourceError, match="Eurostat error"):
        eurostat.parse_payload(b'{"error": {"status": 400, "label": "bad filter"}}')


def test_worldbank_request_uses_iso3_codes_and_date_range():
    settings = load_settings()
    client = worldbank.WorldBankClient(None, "https://wb/", settings.http, ["GRC", "IRL"], 2025)
    url, params = client.build_request(settings.indicators["gdp_growth"])
    assert url == "https://wb/country/GRC;IRL/indicator/NY.GDP.MKTP.KD.ZG"
    assert ("date", "2019:2025") in params


def test_worldbank_summary_ignores_null_values():
    body = json.dumps(
        [{"pages": 1}, [{"date": "2025", "value": None}, {"date": "2024", "value": 2.1}]]
    ).encode()
    summary = worldbank.summarize(worldbank.parse_payload(body))
    assert (summary.observation_count, summary.latest_period) == (1, "2024")


def test_worldbank_error_message_is_an_error():
    with pytest.raises(SourceError, match="World Bank error"):
        worldbank.parse_payload(b'[{"message": [{"id": "120", "value": "Invalid value"}]}]')


def test_worldbank_multiple_pages_is_an_error():
    with pytest.raises(SourceError, match="pages"):
        worldbank.parse_payload(json.dumps([{"pages": 2}, []]).encode())
