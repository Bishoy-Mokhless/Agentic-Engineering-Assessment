"""Dashboard smoke tests in a real headless browser (D-45).

They check the main user paths, not every pixel:
    the page loads with data · a filter change updates the view · empty and error states ·
    each tab shows its content · basic accessibility (labels, keyboard tabs, table twins).
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui

SEGMENT_DISABLED_HINT = (
    "Segments apply to hire cohorts only. Regretted turnover is measured for all employees."
)


def open_dashboard(page: Page, server_url: str) -> None:
    """Open the Explore view directly by its address (D-87: Overview is the landing view)."""
    page.goto(server_url + "/#explore")
    expect(page.locator("[data-testid=rate-tile]").first).to_be_visible()


def choose_segment(page: Page, choices: dict) -> None:
    """Open the segment panel, pick one value per field, apply (D-86).

    Example: choose_segment(page, {"employment_type": "Fixed Term", "career_level": "Manager"})
    """
    page.click("#f-segment")
    expect(page.locator("#segment-panel")).to_be_visible()
    for dimension, value in choices.items():
        page.select_option("#seg-" + dimension, value)
    page.click("#seg-apply")
    expect(page.locator("#segment-panel")).to_be_hidden()


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
    choose_segment(page, {"employment_type": "Fixed Term"})
    expect(page.locator("#explore-label")).to_contain_text("employment_type = Fixed Term")
    expect(page.locator("[data-testid=rate-tile]").first).not_to_have_text(company)


def test_turnover_objective_disables_the_segment_filter(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "REGRETTED_TURNOVER_12M")
    expect(page.locator("#f-segment")).to_be_disabled()
    expect(page.locator(".segment-field")).to_have_attribute("title", SEGMENT_DISABLED_HINT)
    expect(page.locator("#f-segment")).to_have_attribute("title", SEGMENT_DISABLED_HINT)
    expect(page.locator("[data-testid=rate-tile]").first).to_contain_text("5.11%")
    page.select_option("#f-objective", "NEW_HIRE_6M")
    expect(page.locator("#f-segment")).to_be_enabled()
    expect(page.locator(".segment-field")).not_to_have_attribute("title", SEGMENT_DISABLED_HINT)
    expect(page.locator("#explore-years")).to_contain_text("2025-12-31")


def test_empty_state_for_a_slice_without_hires(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "SENIOR_HIRE_12M")
    choose_segment(page, {"career_level": "Manager"})  # senior = Senior Leader only (D-14)
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
    page.goto(server_url + "/#explore")
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
    page.click("#nav-evidence")
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


def test_explore_finding_explains_an_inconclusive_verdict(page: Page, server_url):
    # D-84/D-85: each tab opens with a plain-language finding built from the data.
    open_dashboard(page, server_url)
    finding = page.locator("#explore-finding")
    expect(finding).to_contain_text("87.5%")
    expect(finding).to_contain_text("1,579 of 1,804 hires")
    expect(finding).to_contain_text("cannot yet say")
    expect(page.locator("#explore-meaning")).to_contain_text("Inconclusive in every year from 2021 to 2025")


def test_explore_finding_follows_the_filters(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "SENIOR_HIRE_12M")
    finding = page.locator("#explore-finding")
    expect(finding).to_contain_text("78.2%")
    expect(finding).to_contain_text("below the 90% target")
    expect(page.locator("#explore-meaning")).to_contain_text("Not met in every year from 2021 to 2024")
    company = finding.inner_text()
    page.select_option("#f-country", "RO")
    expect(finding).to_contain_text("in Romania")
    expect(finding).not_to_have_text(company)


def test_explore_finding_for_turnover(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "REGRETTED_TURNOVER_12M")
    finding = page.locator("#explore-finding")
    expect(finding).to_contain_text("5.11%")
    expect(finding).to_contain_text("so the target is met")
    expect(page.locator("#explore-meaning")).to_contain_text("5 of 5 years")


def test_understand_finding_summarises_all_objectives(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#tab-understand")
    finding = page.locator("#understand-finding")
    expect(finding).to_contain_text("senior-hire retention is not met")
    expect(finding).to_contain_text("regretted turnover is met")
    expect(page.locator("#understand-meaning")).to_contain_text("Unemployment rate fell in 5 of 6 countries")


def test_challenge_finding_counts_the_formal_tests(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#tab-challenge")
    finding = page.locator("#challenge-finding")
    expect(finding).to_contain_text("None of the 4 formal within-country tests")
    expect(page.locator("#challenge-meaning")).to_contain_text("associative, not causal")


def test_trust_finding_summarises_reconciliation_and_sensitivity(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#nav-evidence")
    finding = page.locator("#trust-finding")
    expect(finding).to_contain_text("2,407 HR rows reconcile to 2,400 employees")
    expect(page.locator("#trust-meaning")).to_contain_text("No verdict changes")


def test_segments_combine_and_show_as_chips(page: Page, server_url):
    # D-86: several fields in one small panel, combined with AND; chips show what is active.
    open_dashboard(page, server_url)
    choose_segment(page, {"employment_type": "Fixed Term", "career_level": "Manager"})
    expect(page.locator("#f-segment")).to_have_text("Fixed Term, Manager")
    chips = page.locator("#segment-chips button")
    expect(chips).to_have_count(2)
    both = "employment_type = Fixed Term and career_level = Manager"
    expect(page.locator("#explore-label")).to_contain_text(both)
    expect(page.locator("[data-testid=rate-tile]").first).to_contain_text("n = 106")


def test_removing_a_chip_removes_that_filter_only(page: Page, server_url):
    open_dashboard(page, server_url)
    choose_segment(page, {"employment_type": "Fixed Term", "career_level": "Manager"})
    page.click("#segment-chips button[data-dimension=career_level]")
    expect(page.locator("#segment-chips button")).to_have_count(1)
    expect(page.locator("[data-testid=rate-tile]").first).to_contain_text("n = 336")
    page.click("#segment-clear-all")
    expect(page.locator("#f-segment")).to_have_text("All employees")
    expect(page.locator("#segment-chips")).to_be_hidden()


def test_business_unit_narrows_the_job_families(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#f-segment")
    page.select_option("#seg-business_unit", "Digital")
    options = page.locator("#seg-job_family option")
    expect(options).to_have_text(["Any", "Data", "Product", "Software"])


def test_escape_closes_the_segment_panel_without_applying(page: Page, server_url):
    open_dashboard(page, server_url)
    page.click("#f-segment")
    page.select_option("#seg-employment_type", "Fixed Term")
    page.keyboard.press("Escape")
    expect(page.locator("#segment-panel")).to_be_hidden()
    expect(page.locator("#f-segment")).to_be_focused()
    expect(page.locator("#f-segment")).to_have_text("All employees")


def test_every_chart_has_a_table_view(page: Page, server_url):
    open_dashboard(page, server_url)
    page.locator("#explore-content details").first.locator("summary").click()
    expect(page.locator("#trend-table tbody tr").first).to_be_visible()
    expect(page.locator("#trend-table")).to_contain_text("2021-Q1")


# --- D-87: Overview / Explore / Evidence -----------------------------------------------------


def test_overview_is_the_landing_view_with_three_objective_cards(page: Page, server_url):
    page.goto(server_url + "/")
    expect(page.locator("#view-overview")).to_be_visible()
    expect(page.locator("#view-explore")).to_be_hidden()
    cards = page.locator("[data-testid=overview-card]")
    expect(cards).to_have_count(3)
    expect(page.locator("[data-objective=NEW_HIRE_6M]")).to_contain_text("87.5%")
    expect(page.locator("[data-objective=NEW_HIRE_6M]")).to_contain_text("Inconclusive")
    expect(page.locator("[data-objective=SENIOR_HIRE_12M]")).to_contain_text("78.2%")
    expect(page.locator("[data-objective=SENIOR_HIRE_12M]")).to_contain_text("Not met")
    expect(page.locator("[data-objective=REGRETTED_TURNOVER_12M]")).to_contain_text("5.11%")
    expect(page.locator("[data-objective=REGRETTED_TURNOVER_12M]")).to_contain_text("Met")


def test_overview_key_findings_are_built_from_the_data(page: Page, server_url):
    page.goto(server_url + "/")
    findings = page.locator("#overview-findings")
    expect(findings).to_contain_text("not met in every year from 2021 to 2024")
    expect(findings).to_contain_text("rose from 3.30% in 2024 to 5.11% in 2025")
    expect(findings).to_contain_text("None of the 12 formal within-country tests")
    expect(findings).to_contain_text("2,407 HR rows reconcile to 2,400 employees")


def test_overview_market_context_describes_each_signal(page: Page, server_url):
    page.goto(server_url + "/")
    market = page.locator("#overview-market")
    expect(market).to_contain_text("Unemployment rate fell in 5 of 6 countries")
    expect(market).to_contain_text("Inflation")
    expect(market).to_contain_text("job vacancy rate")


def test_an_overview_card_opens_that_objective_in_explore(page: Page, server_url):
    page.goto(server_url + "/")
    page.click("[data-objective=SENIOR_HIRE_12M]")
    expect(page.locator("#view-explore")).to_be_visible()
    expect(page.locator("#f-objective")).to_have_value("SENIOR_HIRE_12M")
    expect(page.locator("#explore-finding")).to_contain_text("78.2%")
    expect(page).to_have_url(re.compile(r"#explore"))


def test_the_address_opens_the_right_view(page: Page, server_url):
    page.goto(server_url + "/#explore/relationships")
    expect(page.locator("#panel-challenge")).to_be_visible()
    expect(page.locator("#tab-challenge")).to_have_attribute("aria-selected", "true")
    page.goto(server_url + "/#evidence")
    expect(page.locator("#panel-trust")).to_be_visible()
    expect(page.locator("#nav-evidence")).to_have_attribute("aria-selected", "true")


# --- Step 9: the headline follows the selected years (D-90) ----------------------------------


def choose_years(page: Page, first: str, last: str) -> None:
    """Set To before From when narrowing to the end, so the range is never reversed on the way."""
    page.select_option("#f-to", last)
    page.select_option("#f-from", first)


def test_explore_headline_follows_the_selected_years(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-country", "BG")
    choose_years(page, "2025", "2025")
    finding = page.locator("#explore-finding")
    expect(finding).to_contain_text("for hires in 2025 (31 of 33 hires stayed)")
    expect(page.locator("[data-testid=rate-tile]").first).to_contain_text("2025 (selected years)")
    # One scope for the whole sentence: 33 mature hires, 31 stayed, so 2 left.
    meaning = page.locator("#explore-meaning")
    expect(meaning).to_contain_text("Of the 2 hires who left within the window, 1 was a voluntary exit.")


def test_overview_cards_follow_the_selected_years(page: Page, server_url):
    page.goto(server_url + "/")
    choose_years(page, "2022", "2023")
    expect(page.locator("[data-objective=NEW_HIRE_6M]")).to_contain_text("86.7%")  # (344+338)/(396+391)
    expect(page.locator("[data-objective=REGRETTED_TURNOVER_12M]")).to_contain_text("3.36%")  # December 2023
    expect(page.locator("[data-objective=REGRETTED_TURNOVER_12M]")).to_contain_text("12 months to 2023-12-31")
    expect(page.locator("#overview-help")).to_contain_text("2022–2023")


def test_market_signals_tiles_follow_the_selected_years(page: Page, server_url):
    page.goto(server_url + "/#explore/signals")
    expect(page.locator("#understand-tiles")).to_contain_text("2021–2025")
    choose_years(page, "2022", "2023")
    tiles = page.locator("#understand-tiles")
    expect(tiles).to_contain_text("New-hire 6-month retention, 2022–2023")
    expect(tiles).to_contain_text("86.7%")
    expect(tiles).to_contain_text("12 months to 2023-12-31")
    expect(page.locator("#understand-finding")).to_contain_text("Across 2022–2023")
    expect(page.locator("#understand-help")).to_contain_text("2022–2023")


def test_overview_says_the_segment_does_not_apply_to_turnover(page: Page, server_url):
    page.goto(server_url + "/")
    choose_segment(page, {"employment_type": "Fixed Term"})
    expect(page.locator("[data-objective=REGRETTED_TURNOVER_12M]")).to_contain_text("All employees")
    expect(page.locator("[data-objective=NEW_HIRE_6M]")).not_to_contain_text("All employees")


def test_turnover_year_table_has_no_hire_only_help(page: Page, server_url):
    open_dashboard(page, server_url)
    expect(page.locator("#years-help-hires")).to_be_visible()
    page.select_option("#f-objective", "REGRETTED_TURNOVER_12M")
    expect(page.locator("#years-help-hires")).to_be_hidden()


# --- Step 9: filters that do not apply are disabled and explained (D-91) ---------------------

PER_VIEW_FILTERS = ["#f-segment", "#f-from", "#f-to", "#f-variant"]


def test_relationships_disables_the_filters_the_formal_tests_ignore(page: Page, server_url):
    page.goto(server_url + "/#explore/relationships")
    expect(page.locator("#challenge-finding")).to_contain_text("formal within-country tests")
    for selector in PER_VIEW_FILTERS:
        expect(page.locator(selector)).to_be_disabled()
    expect(page.locator("#f-country")).to_be_enabled()  # still highlights that country's points
    note = page.locator("#filter-scope-note")
    expect(note).to_be_visible()
    expect(note).to_contain_text("all years")
    expect(page.locator("#f-from").locator("xpath=..")).to_have_attribute("title", re.compile("all years"))
    page.click("#tab-explore")
    for selector in PER_VIEW_FILTERS:
        expect(page.locator(selector)).to_be_enabled()
    expect(note).to_be_hidden()


def test_evidence_hides_the_filters_and_has_its_own_objective(page: Page, server_url):
    # D-93: Evidence hides the filter row (and the segment chips) but keeps the note.
    open_dashboard(page, server_url)
    choose_segment(page, {"employment_type": "Fixed Term"})
    page.click("#nav-evidence")
    expect(page.locator("#trust-sensitivity-summary")).to_contain_text("New-hire")
    expect(page.locator("#filters")).to_be_hidden()
    expect(page.locator("#segment-bar")).to_be_hidden()
    expect(page.locator("#filter-scope-note")).to_have_text(
        "Evidence covers the whole data set, so the filters do not apply here."
    )
    page.click("#nav-overview")
    expect(page.locator("#filters")).to_be_visible()
    expect(page.locator("#segment-bar")).to_be_visible()  # the chosen segment is still there
    expect(page.locator("#filter-scope-note")).to_be_hidden()
    page.click("#nav-evidence")
    page.select_option("#e-objective", "SENIOR_HIRE_12M")
    expect(page.locator("#trust-sensitivity-summary")).to_contain_text("Senior-hire")
    expect(page.locator("#trust-meaning")).to_contain_text("senior-hire")


def test_a_segment_survives_a_visit_to_relationships(page: Page, server_url):
    open_dashboard(page, server_url)
    choose_segment(page, {"employment_type": "Fixed Term"})
    page.click("#tab-challenge")
    expect(page.locator("#f-segment")).to_be_disabled()
    page.click("#tab-explore")
    expect(page.locator("#segment-chips")).to_contain_text("Fixed Term")
    expect(page.locator("#explore-label")).to_contain_text("employment_type = Fixed Term")


# --- Step 9: findings the brief asks for (D-92) ----------------------------------------------


def test_explore_shows_whether_the_verdict_holds_across_segments(page: Page, server_url):
    open_dashboard(page, server_url)
    stability = page.locator("#segments-finding")
    expect(stability).to_contain_text("holds in 7 of 9 segments")
    expect(stability).to_contain_text("Permanent")
    expect(page.locator("#explore-segments")).to_contain_text("Business unit")
    page.select_option("#f-objective", "SENIOR_HIRE_12M")
    expect(stability).to_contain_text("holds in all 6 segments")
    page.select_option("#f-objective", "REGRETTED_TURNOVER_12M")
    expect(page.locator("#segments-card")).to_be_hidden()


def test_overview_findings_add_segment_stability_and_data_health(page: Page, server_url):
    page.goto(server_url + "/")
    findings = page.locator("#overview-findings")
    expect(findings).to_contain_text("not met in all 6 segments")
    expect(findings).to_contain_text("met for Permanent")
    expect(findings).to_contain_text("changes no verdict")


def test_explore_says_what_further_evidence_would_settle_it(page: Page, server_url):
    open_dashboard(page, server_url)
    next_step = page.locator("#explore-next")
    expect(next_step).to_contain_text(re.compile(r"about [\d,]+ mature hires"))
    page.select_option("#f-objective", "SENIOR_HIRE_12M")
    expect(next_step).to_contain_text("exit reasons")
    page.select_option("#f-objective", "REGRETTED_TURNOVER_12M")
    expect(next_step).to_contain_text("hired since 2020")
    page.click("#tab-challenge")
    expect(page.locator("#challenge-meaning")).to_contain_text("longer history")


def test_turnover_explains_the_early_2021_ramp_up(page: Page, server_url):
    open_dashboard(page, server_url)
    page.select_option("#f-objective", "REGRETTED_TURNOVER_12M")
    meaning = page.locator("#explore-meaning")
    expect(meaning).to_contain_text("ramp-up")
    page.select_option("#f-from", "2023")
    expect(meaning).not_to_contain_text("ramp-up")
