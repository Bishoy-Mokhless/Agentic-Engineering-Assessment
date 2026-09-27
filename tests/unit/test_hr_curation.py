"""HR business rules (D-07..D-14, D-57, D-72, D-73): one test per rule, using tiny hand-made rows."""

from datetime import date

import pandas as pd
import pytest
from hr_rows import COUNTRIES, LEVELS, row

from retention.domain.errors import CurationError
from retention.domain.quality import Flag, MetricStatus, metric_status_for
from retention.service.hr_curation import curate_employees, curate_objectives, source_shaped_events


def curate(*rows):
    events = source_shaped_events(pd.DataFrame(list(rows)), "hr/test")
    return curate_employees(events, COUNTRIES, LEVELS)


def one(*rows):
    """Curate and return the single employee as a dict, plus its issue flags."""
    result = curate(*rows)
    assert len(result.employees) == 1
    return result.employees.iloc[0].to_dict(), list(result.issues["flag"])


# --- source-shaped ----------------------------------------------------------------------------


def test_source_shaped_adds_only_line_numbers_and_snapshot():
    events = source_shaped_events(pd.DataFrame([row(), row("ACP000002")]), "hr/2025-12-31")
    assert list(events["source_row"]) == [2, 3]  # CSV line numbers; line 1 is the header
    assert list(events["source_snapshot"]) == ["hr/2025-12-31", "hr/2025-12-31"]
    assert events.iloc[0]["hire_date"] == "2023-01-10"  # still text, unchanged


# --- D-07 duplicates --------------------------------------------------------------------------


def test_exact_duplicate_is_removed_and_logged():
    result = curate(row(), row())
    assert len(result.employees) == 1
    assert result.duplicates_removed == 1
    issue = result.issues.iloc[0]
    assert issue["flag"] == "DUPLICATE_ROW" and issue["source_row"] == 2
    assert "exact copy of row 3" in issue["detail"]  # tie on record_updated_at -> later file row kept


def test_duplicate_keeps_latest_record_updated_at_even_if_earlier_in_file():
    newer = row(record_updated_at="2025-12-30", termination_date="2025-06-01", termination_type="Voluntary",
                regretted_exit="true")  # fmt: skip
    older = row(record_updated_at="2025-12-21")
    result = curate(newer, older)
    kept = result.employees.iloc[0]
    assert kept["termination_type"] == "Voluntary"
    assert "older version" in result.issues.iloc[0]["detail"]


# --- D-08 country codes -----------------------------------------------------------------------


def test_eurostat_style_greece_code_is_mapped():
    employee, flags = one(row(country_code="EL"))
    assert employee["country_code"] == "GR" and employee["country_code_source"] == "EL"
    assert flags == ["COUNTRY_CODE_MAPPED"]
    assert employee["metric_status"] == "INCLUDED"


def test_blank_country_becomes_unknown_but_stays_included():
    employee, flags = one(row(country_code=""))
    assert employee["country_code"] == "Unknown"
    assert flags == ["UNKNOWN_COUNTRY"]
    assert employee["metric_status"] == "INCLUDED"  # counts in company totals


def test_country_code_without_mapping_stops_with_clear_message():
    with pytest.raises(CurationError, match="country_code 'FR' has no 'hr' row"):
        curate(row(country_code="FR"))


# --- D-13 career level ------------------------------------------------------------------------


def test_sr_mgmt_is_mapped_to_senior_leader_keeping_the_original():
    employee, flags = one(row(career_level="Sr Mgmt"))
    assert employee["career_level"] == "Senior Leader" and employee["career_level_source"] == "Sr Mgmt"
    assert flags == ["CAREER_LEVEL_MAPPED"]


# --- D-09 dates -------------------------------------------------------------------------------


def test_missing_hire_date_is_excluded():
    employee, flags = one(row(hire_date=""))
    assert flags == ["MISSING_HIRE_DATE"]
    assert employee["metric_status"] == "EXCLUDED"


def test_termination_before_hire_is_excluded_not_repaired():
    employee, flags = one(
        row(
            hire_date="2023-10-04",
            termination_date="2023-09-24",
            termination_type="Voluntary",
            regretted_exit="true",
        )  # fmt: skip
    )
    assert flags == ["TERM_BEFORE_HIRE"]
    assert employee["metric_status"] == "EXCLUDED"
    assert employee["hire_date"] == date(2023, 10, 4)  # dates kept as delivered


def test_bad_date_text_stops_with_row_number():
    with pytest.raises(CurationError, match="HR row 2: hire_date '10/01/2023'"):
        curate(row(hire_date="10/01/2023"))


# --- D-10 / D-57 / D-11 exits with a blank type -----------------------------------------------


def test_blank_type_exactly_90_days_after_hire_is_quarantined():
    employee, flags = one(row(hire_date="2021-10-07", termination_date="2022-01-05"))  # 90 days
    assert flags == ["UNVERIFIED_EXIT"]
    assert employee["metric_status"] == "QUARANTINED"
    assert employee["termination_type"] == "Unknown"
    assert employee["regretted_exit"] == "UNKNOWN"  # no second flag: the exit itself is quarantined


def test_blank_type_89_days_is_only_a_warning():
    employee, flags = one(row(hire_date="2021-10-07", termination_date="2022-01-04", regretted_exit="false"))
    assert flags == ["MISSING_TERMINATION_TYPE"]
    assert employee["metric_status"] == "INCLUDED"


def test_blank_type_with_normal_tenure_is_kept_as_unknown_type():
    employee, flags = one(row(hire_date="2022-01-08", termination_date="2024-08-08", regretted_exit="false"))
    assert flags == ["MISSING_TERMINATION_TYPE"]
    assert employee["termination_type"] == "Unknown"
    assert employee["regretted_exit"] == "FALSE"
    assert employee["metric_status"] == "INCLUDED"


def test_unknown_termination_type_text_stops_the_run():
    with pytest.raises(CurationError, match="unknown termination_type 'Retired'"):
        curate(row(termination_date="2024-01-01", termination_type="Retired"))


# --- D-12 / D-72 regretted and not-applicable -------------------------------------------------


def test_active_employee_gets_not_applicable_not_unknown():
    employee, flags = one(row())
    assert employee["termination_type"] == "NOT_APPLICABLE"
    assert employee["regretted_exit"] == "NOT_APPLICABLE"
    assert employee["termination_date"] is None or pd.isna(employee["termination_date"])
    assert flags == []


def test_voluntary_exit_with_blank_regretted_is_unknown_never_false():
    employee, flags = one(row(termination_date="2024-11-26", termination_type="Voluntary"))
    assert employee["regretted_exit"] == "UNKNOWN"
    assert flags == ["REGRETTED_UNKNOWN"]
    assert employee["metric_status"] == "INCLUDED"


def test_regretted_true_false_are_normalised():
    true_row = row(
        "ACP000001", termination_date="2024-01-01", termination_type="Voluntary", regretted_exit="true"
    )
    false_row = row("ACP000002", termination_date="2024-01-01", termination_type="Involuntary",
                    regretted_exit="false")  # fmt: skip
    result = curate(true_row, false_row)
    assert list(result.employees["regretted_exit"]) == ["TRUE", "FALSE"]


def test_regretted_on_active_employee_stops_the_run():
    with pytest.raises(CurationError, match="without a termination_date"):
        curate(row(regretted_exit="true"))


# --- D-73 metric status -----------------------------------------------------------------------


def test_most_severe_flag_wins():
    assert metric_status_for([]) == MetricStatus.INCLUDED
    assert metric_status_for([Flag.COUNTRY_CODE_MAPPED]) == MetricStatus.INCLUDED
    assert metric_status_for([Flag.UNVERIFIED_EXIT, Flag.UNKNOWN_COUNTRY]) == MetricStatus.QUARANTINED
    assert metric_status_for([Flag.UNVERIFIED_EXIT, Flag.MISSING_HIRE_DATE]) == MetricStatus.EXCLUDED


def test_objectives_are_typed():
    source = pd.DataFrame(
        [{"objective_id": "NEW_HIRE_6M", "direction": "at_least", "target_value": "0.86",
          "effective_from": "2021-01-01", "effective_to": "2025-12-31", "source_snapshot": "hr/x"}]
    )  # fmt: skip
    objectives = curate_objectives(source)
    assert objectives.iloc[0]["target_value"] == 0.86
    assert objectives.iloc[0]["effective_from"] == date(2021, 1, 1)
