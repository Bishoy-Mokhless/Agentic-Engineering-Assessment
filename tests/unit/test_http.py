"""The shared HTTP layer (D-47): retry policy, retry counting and readable failures. No internet:
a tiny local server answers instead of Eurostat or the World Bank (F-21, D-99)."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

from retention.client.http import SourceError, build_session, http_get
from retention.config import HttpSettings

FAST = HttpSettings(timeout_seconds=5, retries=3, backoff_factor=0)


def serve(answers):
    """Start a local server that answers each GET with the next status code in `answers`."""
    remaining = list(answers)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status = remaining.pop(0) if remaining else 200
            body = b'{"ok": true}' if status == 200 else b"service unavailable"
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep test output quiet
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/data"


def local_session(http):
    """The real session, with its retry adapter also used for the local http:// test server."""
    session = build_session(http)
    session.mount("http://", session.get_adapter("https://example.org"))
    return session


def test_session_retries_on_server_errors_with_backoff():
    retry = (
        build_session(HttpSettings(timeout_seconds=30, retries=3, backoff_factor=1.0))
        .get_adapter("https://x")
        .max_retries
    )
    assert retry.total == 3 and retry.backoff_factor == 1.0
    assert {429, 500, 502, 503, 504} <= set(retry.status_forcelist)


def test_temporary_503s_are_retried_and_counted():
    server, url = serve([503, 503, 200])
    try:
        result = http_get(local_session(FAST), url, [], FAST)
    finally:
        server.shutdown()
    assert result.http_status == 200 and result.body == b'{"ok": true}'
    assert result.retry_count == 2


def test_an_error_that_outlasts_the_retries_is_a_source_error():
    server, url = serve([503] * 10)
    try:
        with pytest.raises(SourceError, match="HTTP 503") as exc_info:
            http_get(local_session(FAST), url, [], FAST)
    finally:
        server.shutdown()
    assert exc_info.value.retry_count == 3


def test_a_wrong_dataset_404_is_not_retried():
    server, url = serve([404])
    try:
        with pytest.raises(SourceError, match="HTTP 404") as exc_info:
            http_get(local_session(FAST), url, [], FAST)
    finally:
        server.shutdown()
    assert exc_info.value.retry_count == 0


def test_no_connection_is_a_source_error(monkeypatch):
    session = local_session(FAST)

    def refuse(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(session, "get", refuse)
    with pytest.raises(SourceError, match="request failed after 3 retries"):
        http_get(session, "http://127.0.0.1:9/data", [], FAST)
