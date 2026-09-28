"""The dashboard is plain files served by FastAPI at / (D-04, D-05); /api routes still win."""

from fastapi.testclient import TestClient

from retention.api.app import DASHBOARD_DIR, create_app


def test_dashboard_page_and_assets_are_served():
    client = TestClient(create_app(dashboard_dir=DASHBOARD_DIR))
    page = client.get("/")
    assert page.status_code == 200
    assert "<title>Asteria Workforce Intelligence</title>" in page.text  # D-87
    for label in ['for="f-objective"', 'for="f-country"', 'for="f-segment"', 'for="f-from"']:
        assert label in page.text  # every filter has a visible label (accessibility)
    assert client.get("/app.js").status_code == 200
    assert client.get("/vendor/chart.umd.min.js").status_code == 200  # stored locally: works offline


def test_api_routes_are_not_hidden_by_the_dashboard_mount():
    client = TestClient(create_app(dashboard_dir=DASHBOARD_DIR))
    assert client.get("/api/health").headers["content-type"].startswith("application/json")


def test_dashboard_never_inserts_api_text_as_html():
    script = (DASHBOARD_DIR / "app.js").read_text(encoding="utf-8")
    assert ".innerHTML" not in script  # API text is always set with textContent
