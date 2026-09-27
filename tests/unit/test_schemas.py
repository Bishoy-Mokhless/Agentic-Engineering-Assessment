"""Schema contracts check structure only and fail with readable messages (D-46, D-61)."""

import pandas as pd
import pytest
from hr_rows import COUNTRIES, LEVELS, row

from retention.domain import schemas
from retention.domain.errors import ContractError
from retention.service.hr_curation import curate_employees, source_shaped_events


def canonical_employees():
    events = source_shaped_events(pd.DataFrame([row(), row("ACP000002", country_code="")]), "hr/test")
    return events, curate_employees(events, COUNTRIES, LEVELS).employees


def test_curated_output_passes_its_contract():
    events, employees = canonical_employees()
    schemas.check_contract(schemas.HR_EVENTS_SOURCE, events, "source-shaped hr_events")
    schemas.check_contract(schemas.employees_schema(["GR", "RO", "BG"]), employees, "canonical employees")


def test_renamed_source_column_is_caught_at_the_door():
    events, _ = canonical_employees()
    renamed = events.rename(columns={"hire_date": "start_date"})
    with pytest.raises(ContractError, match="source-shaped hr_events broke its schema contract"):
        schemas.check_contract(schemas.HR_EVENTS_SOURCE, renamed, "source-shaped hr_events")


def test_unknown_code_value_names_column_and_value():
    _, employees = canonical_employees()
    employees.loc[0, "metric_status"] = "MAYBE"
    with pytest.raises(ContractError) as error:
        schemas.check_contract(schemas.employees_schema(["GR", "RO", "BG"]), employees, "canonical employees")
    assert "metric_status" in str(error.value) and "MAYBE" in str(error.value)


def test_duplicate_employee_key_is_rejected():
    _, employees = canonical_employees()
    employees.loc[1, "employee_id"] = employees.loc[0, "employee_id"]
    with pytest.raises(ContractError, match="employee_id"):
        schemas.check_contract(schemas.employees_schema(["GR", "RO", "BG"]), employees, "canonical employees")
