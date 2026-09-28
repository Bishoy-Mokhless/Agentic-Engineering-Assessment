"""API tests through FastAPI's TestClient (D-44). Spring analogy: MockMvc / @WebMvcTest.

The real offline pipeline builds the data once into a temp folder; every endpoint is then called
like a browser would. No network: offline replay data only.
"""

import math

import pytest
from fastapi.testclient import TestClient

from retention.api.app import create_app
from retention.config import load_settings
from retention.pipeline.job import run_pipeline


def temp_settings(root):
    settings = load_settings()
    settings.paths.source_shaped = root / "curated" / "source_shaped"
    settings.paths.canonical = root / "curated" / "canonical"
    settings.paths.analytical = root / "curated" / "analytical"
    settings.paths.build_tmp = root / ".tmp"
    settings.analysis.bootstrap_iterations = 50  # fast; CI widths are not asserted here
    return settings


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    settings = temp_settings(tmp_path_factory.mktemp("api"))
    assert run_pipeline(settings, "offline") == 0
    return TestClient(create_app(settings, dashboard_dir=None))


@pytest.fixture
def empty_client(tmp_path):
    """An app whose data has never been built."""
    return TestClient(create_app(temp_settings(tmp_path), dashboard_dir=None))


def get_ok(client, url):
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.json()


# --- health and filters -----------------------------------------------------------------------


def test_health_reports_ok_and_the_building_run(client):
    body = get_ok(client, "/api/health")
    assert body["status"] == "ok"
    assert body["data_built_by_run"].startswith("run-")
    assert body["as_of_date"] == "2025-12-31"
    assert body["sources"]["unemployment"] == "replayed"


def test_filters_list_every_dropdown_value(client):
    body = get_ok(client, "/api/filters")
    codes = [country["code"] for country in body["countries"]]
    assert codes == ["ALL", "GR", "RO", "PL", "IT", "IE", "BG"]
    assert body["segments"]["employment_type"] == ["Fixed Term", "Permanent"]
    assert [o["objective_id"] for o in body["objectives"]] == [
        "NEW_HIRE_6M",
        "SENIOR_HIRE_12M",
        "REGRETTED_TURNOVER_12M",
    ]
    assert body["quarters"][0] == "2021-Q1"


# --- retention objectives ---------------------------------------------------------------------


def test_cohorts_whole_period_headline(client):
    body = get_ok(client, "/api/retention/cohorts?objective=SENIOR_HIRE_12M&grain=period")
    row = body["rows"][0]
    assert (row["retained"], row["n"], row["status"]) == (208, 266, "not_met")
    assert body["objective"]["target"] == 0.9
    assert "SENIOR_HIRE_12M" in body["objective"]["label"]


def test_quarter_rows_have_no_verdict_and_json_has_no_nan(client):
    body = get_ok(client, "/api/retention/cohorts?objective=NEW_HIRE_6M&grain=quarter&country=RO")
    assert len(body["rows"]) == 20  # 2021-Q1 .. 2025-Q4
    last = body["rows"][-1]  # 2025-Q4: every hire still inside the 6-month window (D-18)
    assert last["period"] == "2025-Q4" and last["n"] == 0 and last["immature_hires"] > 0
    assert last["rate"] is None
    for row in body["rows"]:
        assert row["status"] is None
        for value in row.values():
            assert not (isinstance(value, float) and math.isnan(value))


def test_segment_filter_recomputes_and_segments_add_up_to_the_total(client):
    total = get_ok(client, "/api/retention/cohorts?grain=period")["rows"][0]
    fixed = get_ok(client, "/api/retention/cohorts?grain=period&segment=employment_type:Fixed Term")
    permanent = get_ok(client, "/api/retention/cohorts?grain=period&segment=employment_type:Permanent")
    assert "computed on request" in fixed["computed"]
    assert fixed["rows"][0]["n"] + permanent["rows"][0]["n"] == total["n"]
    assert fixed["rows"][0]["retained"] + permanent["rows"][0]["retained"] == total["retained"]


def test_several_segments_combine_with_and(client):
    # D-86: repeat `segment` to combine fields. Fixed Term AND Manager = 106 mature new hires (2021-2025).
    both = "segment=employment_type:Fixed Term&segment=career_level:Manager"
    url = "/api/retention/cohorts?grain=period&" + both
    body = get_ok(client, url)
    assert body["rows"][0]["n"] == 106
    assert body["filters"]["segment"] == ["employment_type:Fixed Term", "career_level:Manager"]
    assert "employment_type = Fixed Term and career_level = Manager" in body["computed"]


def test_the_same_segment_field_twice_is_rejected(client):
    url = "/api/retention/cohorts?segment=employment_type:Fixed Term&segment=employment_type:Permanent"
    response = client.get(url)
    assert response.status_code == 400
    assert "employment_type is given more than once" in response.json()["error"]["message"]


def test_filters_list_the_job_families_of_each_business_unit(client):
    body = get_ok(client, "/api/filters")
    assert body["job_families_by_unit"]["Digital"] == ["Data", "Product", "Software"]


def test_segment_with_no_hires_returns_an_empty_list_not_an_error(client):
    # Senior hires are Senior Leaders by definition (D-14), so career_level Manager has none.
    body = get_ok(client, "/api/retention/cohorts?objective=SENIOR_HIRE_12M&segment=career_level:Manager")
    assert body["rows"] == []


def test_year_range_filter(client):
    body = get_ok(client, "/api/retention/cohorts?grain=year&year_from=2022&year_to=2023")
    assert [row["period"] for row in body["rows"]] == ["2022", "2023"]


def test_whole_period_row_follows_a_narrowed_year_range(client):
    # D-90: the headline row covers the selected hire years, recomputed with the same SQL (D-77).
    years = get_ok(client, "/api/retention/cohorts?grain=year&year_from=2022&year_to=2023")["rows"]
    body = get_ok(client, "/api/retention/cohorts?grain=period&year_from=2022&year_to=2023")
    row = body["rows"][0]
    assert len(body["rows"]) == 1
    assert row["period"] == "2022-2023"
    assert row["n"] == sum(year["n"] for year in years)
    assert row["retained"] == sum(year["retained"] for year in years)
    assert row["exits_voluntary"] == sum(year["exits_voluntary"] for year in years)
    assert row["status"] in ("met", "not_met", "inconclusive")
    assert "hire years 2022-2023" in body["computed"]


def test_one_selected_year_gives_the_same_numbers_as_its_year_row(client):
    url = "/api/retention/cohorts?grain={}&country=BG&year_from=2025&year_to=2025"
    year = get_ok(client, url.format("year"))["rows"][0]
    row = get_ok(client, url.format("period"))["rows"][0]
    assert row["period"] == "2025"
    for key in ["n", "retained", "immature_hires", "ci_low", "ci_high", "status"]:
        assert row[key] == year[key], key


def test_full_year_range_keeps_the_precomputed_whole_period_row(client):
    body = get_ok(client, "/api/retention/cohorts?grain=period&year_from=2021&year_to=2025")
    assert body["rows"][0]["period"] == "2021-2025"
    assert body["computed"] == "precomputed by the pipeline"


def test_narrowed_years_combine_with_a_segment(client):
    url = "/api/retention/cohorts?grain={}&year_from=2024&year_to=2025&segment=employment_type:Fixed Term"
    years = get_ok(client, url.format("year"))["rows"]
    body = get_ok(client, url.format("period"))
    assert body["rows"][0]["n"] == sum(year["n"] for year in years)
    assert "employment_type = Fixed Term" in body["computed"] and "hire years 2024-2025" in body["computed"]


def test_segment_stability_gives_a_verdict_per_segment_value(client):
    # D-92: does the whole-period verdict hold in every employment type, career level and business unit?
    body = get_ok(client, "/api/retention/segments?objective=NEW_HIRE_6M")
    overall = body["overall"]
    assert (overall["n"], overall["status"]) == (1804, "inconclusive")
    assert body["dimensions"] == ["employment_type", "career_level", "business_unit"]
    for dimension in body["dimensions"]:
        rows = [row for row in body["rows"] if row["dimension"] == dimension]
        assert sum(row["n"] for row in rows) == overall["n"]  # every mature hire is in exactly one value
    agreements = {"same", "clearer", "less_certain", "opposite", "no_data"}
    for row in body["rows"]:
        assert row["agreement"] in agreements
        assert row["status"] in ("met", "not_met", "inconclusive", None)
    assert sum(body["counts"].values()) == len(body["rows"])


def test_segment_stability_skips_fields_with_one_value_or_already_filtered(client):
    senior = get_ok(client, "/api/retention/segments?objective=SENIOR_HIRE_12M")
    assert "career_level" not in senior["dimensions"]  # senior = Senior Leader only (D-14)
    filters = "segment=employment_type:Fixed Term&year_from=2024&year_to=2025"
    fixed = get_ok(client, "/api/retention/segments?" + filters)
    assert "employment_type" not in fixed["dimensions"]
    base = get_ok(client, "/api/retention/cohorts?grain=period&" + filters)
    assert fixed["overall"]["n"] == base["rows"][0]["n"]
    units = [row for row in fixed["rows"] if row["dimension"] == "business_unit"]
    assert sum(row["n"] for row in units) == fixed["overall"]["n"]


def test_segment_stability_rejects_turnover(client):
    response = client.get("/api/retention/segments?objective=REGRETTED_TURNOVER_12M")
    assert response.status_code == 400


def test_turnover_december_values(client):
    body = get_ok(client, "/api/retention/turnover?year_end_only=true")
    values = [(row["month_end"], row["regretted_exits"], row["status"]) for row in body["rows"]]
    assert values[0] == ("2021-12-31", 23, "met")
    assert values[-1] == ("2025-12-31", 82, "met")


def test_turnover_monthly_rows_have_status_only_in_december(client):
    rows = get_ok(client, "/api/retention/turnover?country=RO&year_from=2024&year_to=2024")["rows"]
    assert len(rows) == 12
    for row in rows:
        assert (row["status"] is not None) == row["month_end"].endswith("-12-31")


def test_sensitivity_changes_no_verdict(client):
    for objective in ["NEW_HIRE_6M", "SENIOR_HIRE_12M", "REGRETTED_TURNOVER_12M"]:
        body = get_ok(client, f"/api/retention/sensitivity?objective={objective}")
        assert body["verdict_changes"] == []
        assert "primary" in body["variants"]


# --- signals ----------------------------------------------------------------------------------


def test_indicators_keep_their_own_frequency(client):
    body = get_ok(client, "/api/indicators?country=GR&indicator=gdp_growth")
    assert [row["period"] for row in body["rows"]][:2] == ["2019", "2020"]
    assert {row["frequency"] for row in body["rows"]} == {"annual"}
    assert "approximations" in body["notes"][0]


def test_association_formal_results_first(client):
    rows = get_ok(client, "/api/association?objective=NEW_HIRE_6M")["rows"]
    assert len(rows) == 12
    assert [row["view"] for row in rows[:4]] == ["within_country"] * 4
    assert all(row["p_holm"] is not None for row in rows[:4])
    assert all(row["p_holm"] is None for row in rows[4:])


def test_association_reports_the_significance_level(client):
    # The dashboard counts "clear association" rows with this value instead of hard-coding it (D-84).
    body = get_ok(client, "/api/association?objective=NEW_HIRE_6M")
    assert body["alpha"] == 0.05


def test_association_points_are_demeaned_and_exclusions_marked(client):
    body = get_ok(client, "/api/association/points?objective=NEW_HIRE_6M&indicator=gdp_growth")
    ireland = [p for p in body["points"] if p["country_code"] == "IE"]
    others = [p for p in body["points"] if p["country_code"] == "GR"]
    assert all(p["excluded_from_tests"] and p["view_x"] is None for p in ireland)
    assert abs(sum(p["view_y"] for p in others)) < 1e-9  # within-country: GR deviations sum to 0
    assert others[0]["source_frequency"] == "annual" and others[0]["age_months"] >= 7


# --- trust ------------------------------------------------------------------------------------


def test_quality_has_reconciliation_issues_and_builds(client):
    body = get_ok(client, "/api/quality")
    assert body["report"]["hr"]["reconciliation"]["employees_out"] == 2400
    assert len(body["issues"]) == 59  # 7 removed duplicates + 52 flags (see the flag counts in Step 3)
    flags = {}
    for issue in body["issues"]:
        flags[issue["flag"]] = flags.get(issue["flag"], 0) + 1
    assert flags["UNVERIFIED_EXIT"] == 12 and flags["DUPLICATE_ROW"] == 7
    assert set(body["builds"]) == {"source_shaped", "canonical", "analytical"}


def test_sources_carry_licence_attribution_and_freshness(client):
    sources = {s["indicator"]: s for s in get_ok(client, "/api/sources")["sources"]}
    assert "CC BY 4.0" in sources["gdp_growth"]["licence"]
    assert "2011/833/EU" in sources["unemployment"]["licence"]
    assert sources["job_vacancy"]["status"] == "replayed"
    assert sources["job_vacancy"]["coverage_last_period"] == "2025-Q4"
    assert sources["hr_pack"]["status"] == "replayed"


# --- errors (D-44: 400 invalid filter, 404 unknown, 503 not built) ------------------------------


@pytest.mark.parametrize(
    ("url", "status", "text"),
    [
        ("/api/retention/cohorts?objective=XX", 404, "unknown objective 'XX'"),
        ("/api/retention/cohorts?country=FR", 404, "unknown country 'FR'"),
        ("/api/retention/cohorts?segment=employment_type:Intern", 404, "unknown employment_type value"),
        ("/api/indicators?indicator=wages", 404, "unknown indicator 'wages'"),
        ("/api/retention/cohorts?grain=month", 400, "grain"),
        ("/api/retention/cohorts?year_from=2025&year_to=2021", 400, "is after year_to"),
        ("/api/retention/cohorts?segment=salary:high", 400, "unknown segment dimension"),
        ("/api/retention/cohorts?segment=employment_type", 400, "dimension:value"),
        ("/api/retention/cohorts?objective=REGRETTED_TURNOVER_12M", 400, "use /api/retention/turnover"),
        ("/api/association/points?view=sideways", 400, "view"),
    ],
)
def test_errors_have_the_right_code_and_a_readable_message(client, url, status, text):
    response = client.get(url)
    assert response.status_code == status
    body = response.json()
    assert text in body["error"]["message"]
    assert body["error"]["code"] in ("not_found", "invalid_filter")


def test_nothing_built_gives_503_with_a_hint_and_health_says_no_data(empty_client):
    response = empty_client.get("/api/retention/cohorts")
    assert response.status_code == 503
    assert "retention run" in response.json()["error"]["message"]
    health = empty_client.get("/api/health").json()
    assert health["status"] == "no_data"


def test_api_docs_are_generated(client):
    assert client.get("/openapi.json").status_code == 200
