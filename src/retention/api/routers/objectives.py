"""GET /api/retention/cohorts, /turnover, /sensitivity (the three objectives)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from retention.api.dependencies import get_settings, get_store, year_query
from retention.config import Settings
from retention.repository.curated_store import CuratedStore
from retention.service import dashboard_queries

router = APIRouter(prefix="/api/retention", tags=["retention"])


@router.get("/cohorts")
def cohorts(
    objective: str = "NEW_HIRE_6M",
    country: str = "ALL",
    grain: Literal["quarter", "year", "period"] = "quarter",
    variant: Literal["primary", "with_unverified_exits"] = "primary",
    segment: list[str] | None = Query(
        default=None,
        description="e.g. employment_type:Fixed Term; repeat it to combine fields with AND (D-86)",
    ),
    year_from: int | None = year_query("first year to include, e.g. 2022"),
    year_to: int | None = year_query("last year to include, e.g. 2024"),
    store: CuratedStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """NEW_HIRE_6M / SENIOR_HIRE_12M cohort rates with n, Wilson CI, status and exit-type breakdown."""
    return dashboard_queries.cohorts(
        store, settings, objective, country, grain, variant, segment, year_from, year_to
    )


@router.get("/segments")
def segments(
    objective: str = "NEW_HIRE_6M",
    country: str = "ALL",
    variant: Literal["primary", "with_unverified_exits"] = "primary",
    segment: list[str] | None = Query(default=None, description="segments already chosen (D-86)"),
    year_from: int | None = year_query("first year to include, e.g. 2022"),
    year_to: int | None = year_query("last year to include, e.g. 2024"),
    store: CuratedStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Segment stability (D-92): the verdict for each employment type, career level and business unit."""
    return dashboard_queries.segment_stability(
        store, settings, objective, country, variant, segment, year_from, year_to
    )


@router.get("/turnover")
def turnover(
    country: str = "ALL",
    variant: Literal["primary", "with_unverified_exits", "unknown_as_regretted"] = "primary",
    year_from: int | None = year_query("first year to include, e.g. 2022"),
    year_to: int | None = year_query("last year to include, e.g. 2024"),
    year_end_only: bool = False,
    store: CuratedStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """REGRETTED_TURNOVER_12M monthly TTM values; status on December rows only."""
    return dashboard_queries.turnover(store, settings, country, variant, year_from, year_to, year_end_only)


@router.get("/sensitivity")
def sensitivity(
    objective: str = "NEW_HIRE_6M",
    store: CuratedStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Primary result next to the sensitivity variants (unverified exits, UNKNOWN regretted)."""
    return dashboard_queries.sensitivity(store, settings, objective)
