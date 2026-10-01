"""Eurostat dissemination API client (D-24, D-25, D-26).

Eurostat answers in "JSON-stat" format. The important parts:
    "id":    ["freq", "unit", "geo", "time"]     names of the dimensions, in order
    "size":  [1, 1, 6, 92]                        how many values each dimension has
    "dimension": {"time": {"category": {"index": {"2019-01": 0, "2019-02": 1, ...}}}}
    "value": {"0": 6.4, "1": 6.1, ...}            the data, keyed by a single flat position number
"""

from __future__ import annotations

import json

import requests

from retention.client.http import FetchResult, PayloadSummary, SourceError, http_get, read_payload
from retention.config import HttpSettings, IndicatorSettings


class EurostatClient:
    provider = "eurostat"

    def __init__(
        self, session: requests.Session, base_url: str, http: HttpSettings, geo_codes: list[str]
    ) -> None:
        self.session = session
        self.base_url = base_url
        self.http = http
        self.geo_codes = geo_codes  # Eurostat's own codes, e.g. "EL" for Greece (D-08)

    def build_request(self, indicator: IndicatorSettings) -> tuple[str, list[tuple[str, str]]]:
        """Return (url, query parameters) for one indicator.

        Example for unemployment:
            url    = ".../data/une_rt_m"
            params = [("s_adj","SA"), ("age","TOTAL"), ..., ("geo","EL"), ("geo","RO"), ...,
                      ("sinceTimePeriod","2019-01")]
        A list of pairs is used (not a dict) because "geo" appears once per country.
        """
        url = self.base_url + indicator.dataset

        params = []
        for name, value in indicator.filters.items():
            params.append((name, value))
        for code in self.geo_codes:
            params.append(("geo", code))
        params.append(("sinceTimePeriod", indicator.since))

        return url, params

    def fetch(self, indicator: IndicatorSettings) -> tuple[FetchResult, PayloadSummary]:
        url, params = self.build_request(indicator)
        result = http_get(self.session, url, params, self.http)
        summary = read_payload(result, parse_payload, summarize)  # a malformed body -> SourceError (D-97)
        return result, summary


def parse_payload(body: bytes) -> dict:
    """Turn the response bytes into a dict, or raise SourceError if it is not usable."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceError(f"response is not valid JSON: {exc}") from exc

    if "error" in data:
        raise SourceError(f"Eurostat error: {data['error']}")
    return data


def summarize(data: dict) -> PayloadSummary:
    """Count the observations and find the latest time period that has a value.

    An HTTP 200 with zero values is treated as a failure: that is exactly what the wrong
    job-vacancy code JOBRATE returned during source research (see D-26).
    """
    # 1. Get the values. Eurostat normally sends a dict {"position": value}; handle a list too.
    values = data.get("value") or {}
    if isinstance(values, list):
        as_dict = {}
        for position, value in enumerate(values):
            if value is not None:
                as_dict[str(position)] = value
        values = as_dict

    if len(values) == 0:
        raise SourceError("returned no observations - check the dataset code and filters")

    # 2. Work out where "time" sits in the flat position number.
    #    Positions are counted like digits of a number: the LAST dimension changes fastest.
    #    "stride" = how much the position grows when time moves one step
    #    (the product of the sizes of all dimensions after "time"; 1 when time is last).
    dimension_names = data["id"]
    dimension_sizes = data["size"]
    time_dim = dimension_names.index("time")
    time_size = dimension_sizes[time_dim]
    stride = 1
    for size in dimension_sizes[time_dim + 1 :]:
        stride = stride * size

    # 3. Find the highest time position that has at least one value.
    latest_time_position = -1
    for key in values:
        time_position = (int(key) // stride) % time_size
        if time_position > latest_time_position:
            latest_time_position = time_position

    # 4. Translate that position back into its label, e.g. 91 -> "2026-08".
    time_labels = data["dimension"]["time"]["category"]["index"]  # {"2019-01": 0, ...}
    latest_period = None
    for label, position in time_labels.items():
        if position == latest_time_position:
            latest_period = label

    return PayloadSummary(observation_count=len(values), latest_period=latest_period)
