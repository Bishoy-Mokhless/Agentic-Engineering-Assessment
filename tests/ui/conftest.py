"""UI test setup (D-45): build the data once, start the real server in a background thread.

Spring analogy: @SpringBootTest(webEnvironment = RANDOM_PORT) + Selenium, with Playwright as the browser.
Needs the browser once: `python -m playwright install chromium`.
"""

import socket
import threading
import time

import pytest
import uvicorn

from retention.api.app import DASHBOARD_DIR, create_app
from retention.config import load_settings
from retention.pipeline.job import run_pipeline


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    # 1. Build real data (offline replay) into a temp folder.
    root = tmp_path_factory.mktemp("ui")
    settings = load_settings()
    settings.paths.source_shaped = root / "curated" / "source_shaped"
    settings.paths.canonical = root / "curated" / "canonical"
    settings.paths.analytical = root / "curated" / "analytical"
    settings.paths.build_tmp = root / ".tmp"
    settings.analysis.bootstrap_iterations = 50
    assert run_pipeline(settings, "offline") == 0

    # 2. Start uvicorn in a background thread on a free port.
    port = free_port()
    config = uvicorn.Config(
        create_app(settings, DASHBOARD_DIR), host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "test server did not start"

    yield f"http://127.0.0.1:{port}"

    # 3. Stop the server.
    server.should_exit = True
    thread.join(timeout=5)
