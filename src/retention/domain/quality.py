"""Quality flags and metric status for the canonical employee table (D-07..D-14, D-57, D-73).

Every flag says what happens to the row (its "effect") and which decision it comes from.
The quality report and the dashboard's Trust view read this table, so the explanation
of each flag lives in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MetricStatus(StrEnum):
    """Does the employee enter the metrics? (D-73)"""

    INCLUDED = "INCLUDED"  # used in primary metrics
    QUARANTINED = "QUARANTINED"  # kept, left out of primary metrics, added back in the sensitivity run (D-10)
    EXCLUDED = "EXCLUDED"  # kept, cannot be placed in any metric (D-09)


class Effect(StrEnum):
    """What a flag does to the row."""

    REMOVED = "removed"  # the row itself is dropped (only exact duplicates, D-07)
    MAPPED = "mapped"  # a code/label was translated through a mapping table
    INFO = "info"  # nothing changes, but the row is limited in some way (e.g. company totals only)
    WARNING = "warning"  # kept in metrics, with a known gap
    QUARANTINED = "quarantined"  # -> metric_status QUARANTINED
    EXCLUDED = "excluded"  # -> metric_status EXCLUDED


class Flag(StrEnum):
    DUPLICATE_ROW = "DUPLICATE_ROW"
    COUNTRY_CODE_MAPPED = "COUNTRY_CODE_MAPPED"
    UNKNOWN_COUNTRY = "UNKNOWN_COUNTRY"
    CAREER_LEVEL_MAPPED = "CAREER_LEVEL_MAPPED"
    MISSING_HIRE_DATE = "MISSING_HIRE_DATE"
    TERM_BEFORE_HIRE = "TERM_BEFORE_HIRE"
    UNVERIFIED_EXIT = "UNVERIFIED_EXIT"
    MISSING_TERMINATION_TYPE = "MISSING_TERMINATION_TYPE"
    REGRETTED_UNKNOWN = "REGRETTED_UNKNOWN"


@dataclass(frozen=True)
class FlagRule:
    effect: Effect
    decision: str
    meaning: str


FLAG_RULES = {
    Flag.DUPLICATE_ROW: FlagRule(
        Effect.REMOVED,
        "D-07",
        "Repeated employee_id; the row with the latest record_updated_at is kept (later file row on a tie).",
    ),
    Flag.COUNTRY_CODE_MAPPED: FlagRule(
        Effect.MAPPED, "D-08", "Non-standard country code mapped (EL -> GR, ROM -> RO)."
    ),
    Flag.UNKNOWN_COUNTRY: FlagRule(
        Effect.INFO,
        "D-08",
        "Blank country: counted in company totals only, not in per-country views or external joins.",
    ),
    Flag.CAREER_LEVEL_MAPPED: FlagRule(Effect.MAPPED, "D-13", "Label 'Sr Mgmt' mapped to 'Senior Leader'."),
    Flag.MISSING_HIRE_DATE: FlagRule(
        Effect.EXCLUDED, "D-09", "No hire date: cannot be placed in a cohort or headcount."
    ),
    Flag.TERM_BEFORE_HIRE: FlagRule(
        Effect.EXCLUDED, "D-09", "Termination date before hire date: impossible, not repaired."
    ),
    Flag.UNVERIFIED_EXIT: FlagRule(
        Effect.QUARANTINED,
        "D-10, D-57, D-67",
        "Unverified exits are quarantined from the primary analysis because their termination "
        "classification is incomplete; a sensitivity analysis assesses the impact of treating them "
        "as valid exits.",
    ),
    Flag.MISSING_TERMINATION_TYPE: FlagRule(
        Effect.WARNING,
        "D-11",
        "Exit with blank termination type but a plausible tenure: kept, type 'Unknown'.",
    ),
    Flag.REGRETTED_UNKNOWN: FlagRule(
        Effect.WARNING,
        "D-12",
        "Exit with blank regretted_exit: kept as UNKNOWN, never imputed; counted separately.",
    ),
}


def metric_status_for(flags: list[Flag]) -> MetricStatus:
    """The most severe effect wins.

    Example: [COUNTRY_CODE_MAPPED]           -> INCLUDED
             [UNVERIFIED_EXIT]               -> QUARANTINED
             [TERM_BEFORE_HIRE, ...anything] -> EXCLUDED
    """
    status = MetricStatus.INCLUDED
    for flag in flags:
        effect = FLAG_RULES[flag].effect
        if effect == Effect.EXCLUDED:
            return MetricStatus.EXCLUDED
        if effect == Effect.QUARANTINED:
            status = MetricStatus.QUARANTINED
    return status
