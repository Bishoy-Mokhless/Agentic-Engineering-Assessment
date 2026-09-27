"""HR business rules: source-shaped events -> canonical employees + quality issues.

Spring analogy: a @Service with one small method per business rule.
D-61: business rules live here in plain Python; Pandera only checks the shape of the result.

Rules, in the order they run:
    1. repeated employee_id: keep the latest record_updated_at            D-07
    2. country codes: EL -> GR, ROM -> RO, blank -> Unknown               D-08
    3. career levels: Sr Mgmt -> Senior Leader                            D-13
    4. dates: missing hire date / termination before hire -> EXCLUDED     D-09
    5. exit: blank type exactly 90 days after hire -> QUARANTINED         D-10, D-57, D-67
             blank type otherwise -> "Unknown" + warning                  D-11
    6. regretted_exit: TRUE / FALSE / UNKNOWN / NOT_APPLICABLE            D-12, D-72
    7. metric_status = the most severe flag                               D-73

Nothing is deleted except exact repeats of the same employee (and those are logged).
Anything the rules have never seen (e.g. a new country code) stops the run with a clear
message, because it needs a human decision, not a silent guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from retention.domain.errors import CurationError
from retention.domain.quality import FLAG_RULES, Flag, metric_status_for

UNVERIFIED_EXIT_DAYS = 90  # D-10: the repeated pattern seen in 12 exits with a blank termination_type
TERMINATION_TYPES = ["Voluntary", "Involuntary", "End of Contract"]
UNKNOWN_TYPE = "Unknown"  # exit happened, type not recorded (D-11)
NOT_APPLICABLE = "NOT_APPLICABLE"  # no exit, so the question does not apply (D-72)
UNKNOWN = "UNKNOWN"  # exit happened, regretted not recorded (D-12)
REGRETTED_VALUES = {"true": "TRUE", "false": "FALSE"}
UNKNOWN_COUNTRY = "Unknown"  # D-08: company totals only

EMPLOYEE_COLUMNS = [
    "employee_id",
    "country_code",
    "country_code_source",
    "business_unit",
    "job_family",
    "career_level",
    "career_level_source",
    "employment_type",
    "hire_date",
    "termination_date",
    "termination_type",
    "regretted_exit",
    "source_system",
    "record_updated_at",
    "quality_flags",
    "metric_status",
    "source_row",
    "source_snapshot",
]
ISSUE_COLUMNS = ["employee_id", "source_row", "flag", "effect", "decision", "detail"]


@dataclass
class HrCurationResult:
    employees: pd.DataFrame
    issues: pd.DataFrame
    rows_in: int
    duplicates_removed: int


# ---------------------------------------------------------------------------------------------
# Source-shaped: the delivered rows as a table, nothing changed (D-71)
# ---------------------------------------------------------------------------------------------


def source_shaped_events(raw: pd.DataFrame, snapshot: str) -> pd.DataFrame:
    """Add lineage columns only: the CSV line number and the raw snapshot it came from.

    Example: first data row -> source_row = 2 (line 1 is the header), source_snapshot = "hr/2025-12-31"
    """
    events = raw.copy()
    events.insert(0, "source_row", range(2, len(events) + 2))
    events["source_snapshot"] = snapshot
    return events


# ---------------------------------------------------------------------------------------------
# Canonical employees
# ---------------------------------------------------------------------------------------------


def curate_employees(
    events: pd.DataFrame, country_codes: dict[str, str], career_levels: dict[str, str]
) -> HrCurationResult:
    """Apply rules 1-7 to the source-shaped events.

    Example: 2,407 rows in -> 7 repeated rows removed -> 2,400 employees, each with a metric_status.
    """
    # 1. Repeated employee_id rows: keep one per employee (D-07).
    kept, issues = remove_duplicates(events)

    # 2-7. Every remaining row becomes one canonical employee plus zero or more issues.
    employees = []
    for row in kept.to_dict("records"):
        employee, found = curate_row(row, country_codes, career_levels)
        employees.append(employee)
        for flag, detail in found:
            issues.append(_issue(row, flag, detail))

    employees_df = pd.DataFrame(employees, columns=EMPLOYEE_COLUMNS)
    employees_df = employees_df.sort_values("employee_id").reset_index(drop=True)
    issues_df = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    issues_df = issues_df.sort_values(["source_row", "flag"]).reset_index(drop=True)

    return HrCurationResult(
        employees=employees_df,
        issues=issues_df,
        rows_in=len(events),
        duplicates_removed=len(events) - len(kept),
    )


def remove_duplicates(events: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Keep one row per employee_id: the latest record_updated_at (later file row on a tie). D-07

    Returns (kept rows in file order, one DUPLICATE_ROW issue per removed row).
    """
    # Sort so that, per employee, the row to keep comes last.
    ordered = events.sort_values(["employee_id", "record_updated_at", "source_row"])
    is_older_copy = ordered.duplicated("employee_id", keep="last")
    removed = ordered[is_older_copy]
    kept = ordered[~is_older_copy].sort_values("source_row")

    # Which row was kept for each employee? {"ACP000045": {...row...}}
    kept_by_id = {}
    for row in kept.to_dict("records"):
        kept_by_id[row["employee_id"]] = row

    # Columns that describe the employee (everything except the file line number).
    business_columns = []
    for column in events.columns:
        if column != "source_row":
            business_columns.append(column)

    issues = []
    for row in removed.to_dict("records"):
        kept_row = kept_by_id[row["employee_id"]]
        same_values = True
        for column in business_columns:
            if row[column] != kept_row[column]:
                same_values = False
        if same_values:
            detail = f"exact copy of row {kept_row['source_row']} (kept)"
        else:
            detail = f"older version of row {kept_row['source_row']} (kept: latest record_updated_at)"
        issues.append(_issue(row, Flag.DUPLICATE_ROW, detail))
    return kept, issues


def curate_row(
    row: dict, country_codes: dict[str, str], career_levels: dict[str, str]
) -> tuple[dict, list[tuple[Flag, str]]]:
    """One source row -> (canonical employee dict, list of (flag, detail))."""
    found = []
    line = row["source_row"]

    # 2. Country (D-08)
    country, country_issue = map_country(row["country_code"], country_codes, line)
    if country_issue:
        found.append(country_issue)

    # 3. Career level (D-13)
    level, level_issue = map_career_level(row["career_level"], career_levels, line)
    if level_issue:
        found.append(level_issue)

    # 4. Dates (D-09)
    hire = parse_date(row["hire_date"], "hire_date", line)
    term = parse_date(row["termination_date"], "termination_date", line)
    date_issue = check_dates(hire, term)
    if date_issue:
        found.append(date_issue)

    # 5. Exit classification (D-10, D-11, D-57)
    termination_type, exit_issue = classify_exit(hire, term, row["termination_type"], line)
    if exit_issue:
        found.append(exit_issue)
    exit_is_unverified = exit_issue is not None and exit_issue[0] == Flag.UNVERIFIED_EXIT

    # 6. Regretted (D-12, D-72)
    regretted, regretted_issue = classify_regretted(
        term, termination_type, row["regretted_exit"], exit_is_unverified, line
    )
    if regretted_issue:
        found.append(regretted_issue)

    # 7. Metric status (D-73)
    flags = []
    for flag, _detail in found:
        flags.append(flag)
    status = metric_status_for(flags)

    employee = {
        "employee_id": row["employee_id"],
        "country_code": country,
        "country_code_source": row["country_code"],
        "business_unit": row["business_unit"],
        "job_family": row["job_family"],
        "career_level": level,
        "career_level_source": row["career_level"],
        "employment_type": row["employment_type"],
        "hire_date": hire,
        "termination_date": term,
        "termination_type": termination_type,
        "regretted_exit": regretted,
        "source_system": row["source_system"],
        "record_updated_at": parse_date(row["record_updated_at"], "record_updated_at", line),
        "quality_flags": ";".join(flags),  # "" when the row is clean
        "metric_status": status.value,
        "source_row": line,
        "source_snapshot": row["source_snapshot"],
    }
    return employee, found


# ---------------------------------------------------------------------------------------------
# The individual rules. Each returns (canonical value, (flag, detail) or None).
# ---------------------------------------------------------------------------------------------


def map_country(code: str, lookup: dict[str, str], line: int) -> tuple[str, tuple[Flag, str] | None]:
    """D-08. Examples: "GR" -> "GR";  "EL" -> "GR" (+ flag);  "" -> "Unknown" (+ flag)."""
    if code == "":
        return UNKNOWN_COUNTRY, (Flag.UNKNOWN_COUNTRY, "country_code is blank")
    if code not in lookup:
        raise CurationError(
            f"HR row {line}: country_code '{code}' has no 'hr' row in config/mappings/country_codes.csv "
            "- add a mapping row (D-08)"
        )
    canonical = lookup[code]
    if canonical != code:
        return canonical, (Flag.COUNTRY_CODE_MAPPED, f"{code} -> {canonical}")
    return canonical, None


def map_career_level(label: str, lookup: dict[str, str], line: int) -> tuple[str, tuple[Flag, str] | None]:
    """D-13. Examples: "Manager" -> "Manager";  "Sr Mgmt" -> "Senior Leader" (+ flag)."""
    if label not in lookup:
        raise CurationError(
            f"HR row {line}: career_level '{label}' is not in config/mappings/career_levels.csv "
            "- add a mapping row (D-13)"
        )
    canonical = lookup[label]
    if canonical != label:
        return canonical, (Flag.CAREER_LEVEL_MAPPED, f"{label} -> {canonical}")
    return canonical, None


def parse_date(text: str, column: str, line: int) -> date | None:
    """ "2024-09-04" -> date(2024, 9, 4);  "" -> None."""
    if text == "":
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise CurationError(f"HR row {line}: {column} '{text}' is not an ISO date (YYYY-MM-DD)") from exc


def check_dates(hire: date | None, term: date | None) -> tuple[Flag, str] | None:
    """D-09. A row without a usable hire date cannot be placed in any metric."""
    if hire is None:
        return Flag.MISSING_HIRE_DATE, "hire_date is blank"
    if term is not None and term < hire:
        gap = (hire - term).days
        return Flag.TERM_BEFORE_HIRE, f"terminated {term} before hire {hire} ({gap} days earlier)"
    return None


def classify_exit(
    hire: date | None, term: date | None, type_text: str, line: int
) -> tuple[str, tuple[Flag, str] | None]:
    """D-10, D-11, D-57, D-72.

    Examples:
        no termination date                         -> "NOT_APPLICABLE"
        "Voluntary"                                 -> "Voluntary"
        blank type, exit exactly 90 days after hire -> "Unknown" + UNVERIFIED_EXIT (quarantined)
        blank type, any other tenure                -> "Unknown" + MISSING_TERMINATION_TYPE (warning)
    """
    # 1. Active employee: there is no exit to classify.
    if term is None:
        if type_text != "":
            raise CurationError(
                f"HR row {line}: termination_type '{type_text}' without a termination_date "
                "- no rule covers this yet; decide how to handle it"
            )
        return NOT_APPLICABLE, None

    # 2. Normal case: a known type.
    if type_text in TERMINATION_TYPES:
        return type_text, None
    if type_text != "":
        raise CurationError(
            f"HR row {line}: unknown termination_type '{type_text}' (expected one of {TERMINATION_TYPES})"
        )

    # 3. Exit with a blank type.
    if hire is None:
        return UNKNOWN_TYPE, (Flag.MISSING_TERMINATION_TYPE, "termination_type is blank")
    tenure_days = (term - hire).days
    if tenure_days == UNVERIFIED_EXIT_DAYS:
        detail = f"termination_type blank and exit exactly {UNVERIFIED_EXIT_DAYS} days after hire"
        return UNKNOWN_TYPE, (Flag.UNVERIFIED_EXIT, detail)
    detail = f"termination_type blank; exit {tenure_days} days after hire"
    return UNKNOWN_TYPE, (Flag.MISSING_TERMINATION_TYPE, detail)


def classify_regretted(
    term: date | None,
    termination_type: str,
    regretted_text: str,
    exit_is_unverified: bool,
    line: int,
) -> tuple[str, tuple[Flag, str] | None]:
    """D-12, D-72.

    Examples:
        no termination date           -> "NOT_APPLICABLE"
        "true" / "false"              -> "TRUE" / "FALSE"
        blank on an exit              -> "UNKNOWN" + REGRETTED_UNKNOWN (never imputed)
        blank on an unverified exit   -> "UNKNOWN" (the exit itself is already quarantined)
    """
    # 1. Active employee.
    if term is None:
        if regretted_text != "":
            raise CurationError(
                f"HR row {line}: regretted_exit '{regretted_text}' on an employee without a termination_date"
            )
        return NOT_APPLICABLE, None

    # 2. A recorded value.
    if regretted_text in REGRETTED_VALUES:
        return REGRETTED_VALUES[regretted_text], None
    if regretted_text != "":
        raise CurationError(
            f"HR row {line}: unexpected regretted_exit '{regretted_text}' (expected true, false or blank)"
        )

    # 3. Blank on an exit: unknown, not false.
    if exit_is_unverified:
        return UNKNOWN, None
    return UNKNOWN, (Flag.REGRETTED_UNKNOWN, f"{termination_type} exit with blank regretted_exit")


def _issue(row: dict, flag: Flag, detail: str) -> dict:
    rule = FLAG_RULES[flag]
    return {
        "employee_id": row["employee_id"],
        "source_row": row["source_row"],
        "flag": flag.value,
        "effect": rule.effect.value,
        "decision": rule.decision,
        "detail": detail,
    }


# ---------------------------------------------------------------------------------------------
# Canonical objectives (targets)
# ---------------------------------------------------------------------------------------------


def curate_objectives(source: pd.DataFrame) -> pd.DataFrame:
    """Type the source-shaped objectives table: target_value -> number, dates -> dates.

    Example: NEW_HIRE_6M, at_least, "0.86" -> 0.86, "2021-01-01" -> date(2021, 1, 1)
    """
    objectives = source.copy()
    try:
        objectives["target_value"] = objectives["target_value"].astype(float)
    except ValueError as exc:
        raise CurationError(f"retention_objectives.csv: target_value is not a number: {exc}") from exc

    for column in ["effective_from", "effective_to"]:
        dates = []
        for position, text in enumerate(objectives[column]):
            dates.append(parse_date(text, column, position + 2))
        objectives[column] = dates
    return objectives
