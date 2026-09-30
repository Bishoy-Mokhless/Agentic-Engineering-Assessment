"""Shared HTTP layer: timeouts + retry with exponential backoff (D-47)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from retention.config import HttpSettings

RETRY_ON_STATUS = (429, 500, 502, 503, 504)  # "too many requests" + temporary server errors


class SourceError(Exception):
    """A source could not deliver usable data. The message is shown to the user as-is."""

    def __init__(self, message: str, retry_count: int = 0) -> None:
        super().__init__(message)
        self.retry_count = retry_count


@dataclass(frozen=True)
class FetchResult:
    url: str  # final URL including query string
    http_status: int
    body: bytes  # exactly what the provider returned (saved untouched to data/raw)
    retry_count: int
    fetched_at: datetime


@dataclass(frozen=True)
class PayloadSummary:
    observation_count: int
    latest_period: str


def build_session(http: HttpSettings) -> requests.Session:
    """Create the one HTTP session used for every API call.

    The retry policy is attached to the session, so every GET automatically gets it.
    """
    retry = Retry(
        total=http.retries,
        backoff_factor=http.backoff_factor,  # waits ~1s, 2s, 4s ...
        status_forcelist=RETRY_ON_STATUS,
        allowed_methods=("GET",),
        respect_retry_after_header=True,
        raise_on_status=False,  # return the last response so we can report its status code
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "retention-assessment/0.1"
    return session


def http_get(
    session: requests.Session, url: str, params: list[tuple[str, str]], http: HttpSettings
) -> FetchResult:
    """GET one URL. Return the raw response bytes, or raise SourceError with a readable message."""
    fetched_at = datetime.now(UTC)

    # 1. Call the API. Retries happen inside session.get (see build_session).
    #    If it still fails after all retries (no connection, timeout...), we land in except.
    try:
        response = session.get(url, params=params, timeout=http.timeout_seconds)
    except requests.RequestException as exc:
        raise SourceError(f"request failed after {http.retries} retries: {exc}", http.retries) from exc

    # 2. Count how many retries were used (urllib3 keeps a history of retried attempts).
    retry_count = 0
    retries = getattr(response.raw, "retries", None)
    if retries is not None:
        retry_count = len(retries.history)

    # 3. Anything other than 200 OK is a failure (e.g. 404 wrong dataset, 503 after all retries).
    if response.status_code != 200:
        short_text = response.text[:200]
        raise SourceError(f"HTTP {response.status_code}: {short_text}", retry_count)

    return FetchResult(
        url=response.url,
        http_status=response.status_code,
        body=response.content,
        retry_count=retry_count,
        fetched_at=fetched_at,
    )
