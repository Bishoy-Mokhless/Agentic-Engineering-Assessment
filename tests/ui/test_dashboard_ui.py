"""Dashboard smoke tests in a real headless browser (D-45).

They check the main user paths, not every pixel:
    the page loads with data · a filter change updates the view · empty and error states ·
    each tab shows its content · basic accessibility (labels, keyboard tabs, table twins).
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


def open_dashboard(page: Page, server_url: str) -> None:
    page.goto(server_url + "/")
    expect(page.locator("[data-testid=rate-tile]").first).to_be_visible()


def test_page_loads_with_data_and_healthy_status(page: Page, server_url):
    open_dashboard(page, server_url)
    expect(page.locator("#health")).to_have_attribute("data-health", "ok")
    expect(page.locator("#as-of")).to_have_text("2025-12-31")
    first_tile = page.locator("[data-testid=rate-tile]").first
    expect(first_tile).to_contain_text("87.5%")  # NEW_HIRE_6M 2021-2025, company
    expect(first_tile).to_contain_text("Inconclusive")


def test_changing_the_objective_updates_the_view(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "SENIOR_HIRE_12M")
    first_tile = page.locator("[data-testid=rate-tile]").first
    expect(first_tile).to_contain_text("78.2%")
    expect(first_tile.locator("[data-status=not_met]")).to_be_visible()
    expect(page.locator("#explore-title")).to_contain_text("Senior-hire")


def test_country_and_segment_filters_change_the_numbers(page: Page, server_url):
    open_dashboard(page, server_url)
    company = page.locator("[data-testid=rate-tile]").first.inner_text()
    page.select_option("#f-country", "RO")
    expect(page.locator("#explore-title")).to_contain_text("Romania")
    page.select_option("#f-segment", "employment_type:Fixed Term")
    expect(page.locator("#explore-label")).to_contain_text("employment_type = Fixed Term")
    expect(page.locator("[data-testid=rate-tile]").first).not_to_have_text(company)


def test_turnover_objective_disables_the_segment_filter(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "REGRETTED_TURNOVER_12M")
    expect(page.locator("#f-segment")).to_be_disabled()
    expect(page.locator("[data-testid=rate-tile]").first).to_contain_text("5.11%")
    expect(page.locator("#explore-years")).to_contain_text("2025-12-31")


def test_empty_state_for_a_slice_without_hires(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "SENIOR_HIRE_12M")
    page.select_option("#f-segment", "career_level:Manager")  # senior = Senior Leader only (D-14)
    message = page.locator("#explore-message")
    expect(message).to_have_attribute("data-kind", "empty")
    expect(message).to_contain_text("No mature hires match these filters")
    expect(page.locator("#explore-content")).to_be_hidden()


def test_error_state_shows_the_api_message(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-from", "2025")
    page.select_option("#f-to", "2021")
    message = page.locator("#explore-message")
    expect(message).to_have_attribute("role", "alert")
    expect(message).to_contain_text("year_from (2025) is after year_to (2021)")


def test_api_outage_is_shown_not_a_blank_page(page: Page, server_url):
    # Simulate the data service being down for every retention call.
    page.route(
        re.compile(r".*/api/retention/.*"),
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"error": {"code": "data_not_built", "message": "run `retention run` first"}}',
        ),
    )
    page.goto(server_url + "/")
    message = page.locator("#explore-message")
    expect(message).to_contain_text("No data yet")
    expect(message).to_have_attribute("role", "alert")


def test_understand_tab_shows_all_objectives_and_a_signal_chart(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#tab-understand")
    expect(page.locator("#understand-tiles [data-testid=rate-tile]")).to_have_count(3)
    page.select_option("#u-indicator", "gdp_growth")
    expect(page.locator("#u-indicator-caption")).to_contain_text("GDP growth")
    page.locator("#panel-understand details").nth(1).locator("summary").click()
    expect(page.locator("#u-indicator-table")).to_contain_text("annual")


def test_challenge_tab_shows_tests_with_uncertainty_and_careful_wording(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#tab-challenge")
    results = page.locator("#challenge-results tbody tr")
    expect(results).to_have_count(12)  # 4 signals x 3 views
    expect(page.locator("#challenge-results tr.formal")).to_have_count(4)
    expect(page.locator("#challenge-label")).to_have_text("NEW_HIRE_6M — Primary association analysis")
    result = page.locator("#challenge-result")
    expect(result).to_contain_text("did not show a clear association")
    expect(result).to_contain_text("Holm-adjusted p")
    page.select_option("#c-view", "pooled")
    expect(result).to_contain_text("Descriptive pooled context — not the primary formal test.")


def test_trust_tab_shows_sources_quality_and_sensitivity(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#tab-trust")
    expect(page.locator("#trust-sources")).to_contain_text("CC BY 4.0")
    expect(page.locator("#trust-sources")).to_contain_text("replayed")
    expect(page.locator("#trust-reconciliation")).to_contain_text("2400 employees (reconciled)")
    expect(page.locator("#trust-flags")).to_contain_text("UNVERIFIED_EXIT")
    expect(page.locator("#trust-sensitivity-summary")).to_contain_text("No verdict changes")


def test_every_filter_has_a_label(page: Page, server_url):
    open_dashboard(page, server_url)
    selects = page.locator("select")
    for index in range(selects.count()):
        select_id = selects.nth(index).get_attribute("id")
        expect(page.locator(f'label[for="{select_id}"]')).to_have_count(1)


def test_tabs_work_with_the_keyboard(page: Page, server_url):
    open_dashboard(page, server_url)
    page.focus("#tab-explore")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#tab-understand")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#panel-understand")).to_be_visible()
    expect(page.locator("#panel-explore")).to_be_hidden()


def test_every_chart_has_a_table_view(page: Page, server_url):
    open_dashboard(page, server_url)
    page.locator("#explore-content details").first.locator("summary").click()
    expect(page.locator("#trend-table tbody tr").first).to_be_visible()
    expect(page.locator("#trend-table")).to_contain_text("2021-Q1")
