"""Turn source period labels into real start/end dates (canonical periods).

Examples:
    period_bounds("2023-02", "monthly")   -> (2023-02-01, 2023-02-28)
    period_bounds("2023-Q1", "quarterly") -> (2023-01-01, 2023-03-31)
    period_bounds("2021", "annual")       -> (2021-01-01, 2021-12-31)

The original label is always kept next to the dates, so an annual value can never be
mistaken for a monthly or quarterly one (frequency integrity, D-31).
"""

from __future__ import annotations

import calendar
from datetime import date

from retention.domain.errors import CurationError


def month_end(year: int, month: int) -> date:
    """Last day of a month, e.g. (2024, 2) -> 2024-02-29."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def period_bounds(label: str, frequency: str) -> tuple[date, date]:
    """Return (first day, last day) of the period the label describes."""
    try:
        if frequency == "monthly":
            # "2023-02"
            year_text, month_text = label.split("-")
            year = int(year_text)
            month = int(month_text)
            return date(year, month, 1), month_end(year, month)

        if frequency == "quarterly":
            # "2023-Q1": quarter 1 = Jan..Mar, 2 = Apr..Jun, 3 = Jul..Sep, 4 = Oct..Dec
            year_text, quarter_text = label.split("-Q")
            year = int(year_text)
            quarter = int(quarter_text)
            first_month = (quarter - 1) * 3 + 1
            last_month = first_month + 2
            return date(year, first_month, 1), month_end(year, last_month)

        if frequency == "annual":
            # "2021"
            year = int(label)
            return date(year, 1, 1), date(year, 12, 31)
    except ValueError as exc:
        raise CurationError(f"period label '{label}' is not a valid {frequency} period") from exc

    raise CurationError(f"unknown frequency '{frequency}' (expected monthly, quarterly or annual)")
