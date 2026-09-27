"""Shared helpers for HR tests: build delivered-style HR rows (all text, like the CSV)."""

COUNTRIES = {"GR": "GR", "RO": "RO", "BG": "BG", "EL": "GR", "ROM": "RO"}  # like the 'hr' rows in the CSV
LEVELS = {"Individual Contributor": "Individual Contributor", "Manager": "Manager",
          "Senior Leader": "Senior Leader", "Sr Mgmt": "Senior Leader"}  # fmt: skip


def row(employee_id="ACP000001", **changes):
    """One delivered HR row (all text, like the CSV). Override any column with keyword arguments."""
    base = {
        "employee_id": employee_id,
        "country_code": "GR",
        "business_unit": "Sales",
        "job_family": "Field Sales",
        "career_level": "Manager",
        "employment_type": "Permanent",
        "hire_date": "2023-01-10",
        "termination_date": "",
        "termination_type": "",
        "regretted_exit": "",
        "source_system": "HCM_A",
        "record_updated_at": "2025-12-20",
    }
    base.update(changes)
    return base
