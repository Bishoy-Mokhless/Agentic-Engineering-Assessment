"""Schema contracts for the source-shaped and canonical tables (D-46, D-61).

Spring analogy: Bean Validation (@NotNull, @Pattern) for whole tables.

D-61: these check STRUCTURE only: columns exist, types, allowed codes, keys are unique.
Business rules (duplicates, bad dates, unverified exits...) are in service/hr_curation.py,
because the data is intentionally imperfect and those rows must be flagged, not rejected.
If a contract fails, the run stops with the table name and the first failing values.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.engines.pandas_engine import Date

from retention.domain.errors import ContractError
from retention.domain.quality import Effect, Flag, MetricStatus

HR_SOURCE_COLUMNS = [
    "employee_id",
    "country_code",
    "business_unit",
    "job_family",
    "career_level",
    "employment_type",
    "hire_date",
    "termination_date",
    "termination_type",
    "regretted_exit",
    "source_system",
    "record_updated_at",
]


def _text_column(nullable: bool = False) -> pa.Column:
    return pa.Column(str, nullable=nullable)


# --- Source-shaped -------------------------------------------------------------------------


def _hr_events_columns() -> dict[str, pa.Column]:
    """source_row, then the 12 delivered columns as text, then source_snapshot."""
    columns = {"source_row": pa.Column(int, unique=True)}
    for name in HR_SOURCE_COLUMNS:
        columns[name] = _text_column()
    columns["source_snapshot"] = _text_column()
    return columns


# The delivered HR file exactly as text. strict=True: a renamed or extra column in a future
# extract fails here, before any rule runs (schema evolution is caught at the door).
HR_EVENTS_SOURCE = pa.DataFrameSchema(_hr_events_columns(), strict=True, ordered=True)

OBJECTIVES_SOURCE = pa.DataFrameSchema(
    {
        "objective_id": pa.Column(str, unique=True),
        "direction": pa.Column(str, pa.Check.isin(["at_least", "at_most"])),
        "target_value": _text_column(),
        "effective_from": _text_column(),
        "effective_to": _text_column(),
    },
    strict=False,
)

# Eurostat tables have different dimension columns per dataset; geo/time/value/status are always there.
EUROSTAT_SOURCE = pa.DataFrameSchema(
    {
        "geo": _text_column(),
        "time": _text_column(),
        "value": pa.Column(float),
        "status": _text_column(nullable=True),
    },
    strict=False,
)

WORLDBANK_SOURCE = pa.DataFrameSchema(
    {
        "indicator_id": _text_column(),
        "countryiso3code": _text_column(),
        "date": _text_column(),
        "value": pa.Column(float, nullable=True),  # World Bank sends null for missing years
        "obs_status": _text_column(nullable=True),
    },
    strict=False,
)


def employees_schema(countries: list[str]) -> pa.DataFrameSchema:
    """Canonical employees: one row per employee_id (the key)."""
    allowed_countries = list(countries) + ["Unknown"]
    statuses = []
    for status in MetricStatus:
        statuses.append(status.value)

    return pa.DataFrameSchema(
        {
            "employee_id": pa.Column(str, unique=True),
            "country_code": pa.Column(str, pa.Check.isin(allowed_countries)),
            "country_code_source": _text_column(),
            "business_unit": _text_column(),
            "job_family": _text_column(),
            "career_level": pa.Column(
                str, pa.Check.isin(["Individual Contributor", "Manager", "Senior Leader"])
            ),
            "career_level_source": _text_column(),
            "employment_type": pa.Column(str, pa.Check.isin(["Permanent", "Fixed Term"])),
            "hire_date": pa.Column(Date, nullable=True),  # null only on MISSING_HIRE_DATE rows
            "termination_date": pa.Column(Date, nullable=True),  # null = active
            "termination_type": pa.Column(
                str,
                pa.Check.isin(["Voluntary", "Involuntary", "End of Contract", "Unknown", "NOT_APPLICABLE"]),
            ),
            "regretted_exit": pa.Column(str, pa.Check.isin(["TRUE", "FALSE", "UNKNOWN", "NOT_APPLICABLE"])),
            "source_system": _text_column(),
            "record_updated_at": pa.Column(Date),
            "quality_flags": _text_column(),  # "" when clean
            "metric_status": pa.Column(str, pa.Check.isin(statuses)),
            "source_row": pa.Column(int, unique=True),
            "source_snapshot": _text_column(),
        },
        strict=True,
        ordered=True,
    )


def _flag_values() -> list[str]:
    values = []
    for flag in Flag:
        values.append(flag.value)
    return values


def _effect_values() -> list[str]:
    values = []
    for effect in Effect:
        values.append(effect.value)
    return values


QUALITY_ISSUES = pa.DataFrameSchema(
    {
        "employee_id": _text_column(),
        "source_row": pa.Column(int),
        "flag": pa.Column(str, pa.Check.isin(_flag_values())),
        "effect": pa.Column(str, pa.Check.isin(_effect_values())),
        "decision": _text_column(),
        "detail": _text_column(),
    },
    strict=True,
    unique=["source_row", "flag"],
)

OBJECTIVES = pa.DataFrameSchema(
    {
        "objective_id": pa.Column(str, unique=True),
        "direction": pa.Column(str, pa.Check.isin(["at_least", "at_most"])),
        "target_value": pa.Column(float, pa.Check.in_range(0, 1)),
        "effective_from": pa.Column(Date),
        "effective_to": pa.Column(Date),
    },
    strict=False,
)


def indicators_schema(countries: list[str], indicator_names: list[str]) -> pa.DataFrameSchema:
    """Canonical indicators: key = (indicator, country_code, period)."""
    return pa.DataFrameSchema(
        {
            "indicator": pa.Column(str, pa.Check.isin(indicator_names)),
            "provider": pa.Column(str, pa.Check.isin(["eurostat", "worldbank"])),
            "dataset": _text_column(),
            "lens": _text_column(),
            "country_code": pa.Column(str, pa.Check.isin(countries)),
            "source_country_code": _text_column(),
            "period": _text_column(),
            "frequency": pa.Column(str, pa.Check.isin(["monthly", "quarterly", "annual"])),
            "period_start": pa.Column(Date),
            "period_end": pa.Column(Date),
            "value": pa.Column(float),
            "unit": _text_column(),
            "obs_status": _text_column(nullable=True),
            "obs_status_label": _text_column(nullable=True),
            "source_snapshot": _text_column(),
            "loaded_at": _text_column(nullable=True),
            "source_last_updated": _text_column(nullable=True),
        },
        strict=True,
        ordered=True,
        unique=["indicator", "country_code", "period"],
    )


def check_contract(schema: pa.DataFrameSchema, table: pd.DataFrame, table_name: str) -> None:
    """Validate a table; on failure raise ContractError naming the table and the failing values.

    Example message:
        canonical employees broke its schema contract (2 problems):
          - column 'country_code' check isin([...]): failing value 'FR' (row 17)
    """
    try:
        schema.validate(table, lazy=True)  # lazy = collect all problems, not just the first
    except pa.errors.SchemaErrors as exc:
        cases = exc.failure_cases
        lines = []
        for case in cases.head(10).to_dict("records"):
            lines.append(
                f"  - column '{case['column']}' check {case['check']}: "
                f"failing value '{case['failure_case']}' (row {case['index']})"
            )
        message = f"{table_name} broke its schema contract ({len(cases)} problems):\n" + "\n".join(lines)
        raise ContractError(message) from exc
