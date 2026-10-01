"""World Bank API v2 client (D-27).

The World Bank answers with a 2-item JSON list:
    [ {"page": 1, "pages": 1, ...},                                   <- paging metadata
      [ {"countryiso3code": "GRC", "date": "2025", "value": 2.1}, ...] ]   <- observations
"""

from __future__ import annotations

import json

import requests

from retention.client.http import FetchResult, PayloadSummary, SourceError, http_get, read_payload
from retention.config import HttpSettings, IndicatorSettings

PAGE_SIZE = 1000  # 6 countries x ~7 years fits in one page; more than one page is treated as an error


class WorldBankClient:
    provider = "worldbank"

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        http: HttpSettings,
        country_codes: list[str],
        end_year: int,
    ) -> None:
        self.session = session
        self.base_url = base_url
        self.http = http
        self.country_codes = country_codes  # World Bank's ISO3 codes, e.g. "GRC" (D-08)
        self.end_year = end_year

    def build_request(self, indicator: IndicatorSettings) -> tuple[str, list[tuple[str, str]]]:
        """Return (url, query parameters).

        Example: .../country/GRC;ROU;POL;ITA;IRL;BGR/indicator/NY.GDP.MKTP.KD.ZG
                 ?format=json&date=2019:2025&per_page=1000
        """
        countries = ";".join(self.country_codes)
        url = f"{self.base_url}country/{countries}/indicator/{indicator.dataset}"
        params = [
            ("format", "json"),
            ("date", f"{indicator.since}:{self.end_year}"),
            ("per_page", str(PAGE_SIZE)),
        ]
        return url, params

    def fetch(self, indicator: IndicatorSettings) -> tuple[FetchResult, PayloadSummary]:
        url, params = self.build_request(indicator)
        result = http_get(self.session, url, params, self.http)
        summary = read_payload(result, parse_payload, summarize)  # a malformed body -> SourceError (D-97)
        return result, summary


def parse_payload(body: bytes) -> list:
    """Turn the response bytes into [metadata, observations], or raise SourceError."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceError(f"response is not valid JSON: {exc}") from exc

    # The World Bank reports errors as [{"message": [...]}] with HTTP 200.
    is_error = isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "message" in data[0]
    if is_error:
        raise SourceError(f"World Bank error: {data[0]['message']}")

    if not isinstance(data, list) or len(data) != 2:
        raise SourceError("unexpected response shape (expected [metadata, observations])")

    pages = int(data[0].get("pages", 1))
    if pages > 1:
        raise SourceError(f"response has {pages} pages; only one page is supported")
    return data


def summarize(data: list) -> PayloadSummary:
    """Count the non-empty observations and find the latest year that has a value."""
    observations = data[1] or []

    count = 0
    latest_year = None
    for row in observations:
        if row.get("value") is None:  # the World Bank lists years with no data as null
            continue
        count = count + 1
        if latest_year is None or row["date"] > latest_year:
            latest_year = row["date"]

    if count == 0:
        raise SourceError("returned no observations - check the indicator code and date range")
    return PayloadSummary(observation_count=count, latest_period=latest_year)
