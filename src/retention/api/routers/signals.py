"""GET /api/indicators, /api/association, /api/association/points (external signals)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from retention.api.dependencies import get_settings, get_store, year_query
from retention.config import Settings
from retention.repository.curated_store import CuratedStore
from retention.service import dashboard_queries

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/indicators")
def indicators(
    country: str | None = None,
    indicator: str | None = None,
    year_from: int | None = year_query("first year to include, e.g. 2022"),
    year_to: int | None = year_query("last year to include, e.g. 2024"),
    store: CuratedStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Indicator series; each value keeps its own period, frequency and publication status."""
    return dashboard_queries.indicators(store, settings, country, indicator, year_from, year_to)


@router.get("/association")
def association(
    objective: str | None = None,
    store: CuratedStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Spearman results: rho, bootstrap CI, n, p, Holm p (formal only), wording and caveats."""
    return dashboard_queries.association(store, settings, objective)


@router.get("/association/points")
def association_points(
    objective: str = "NEW_HIRE_6M",
    indicator: str = "unemployment",
    view: Literal["within_country", "pooled", "time_adjusted"] = "within_country",
    analysis_set: Literal["formal", "descriptive"] = "formal",
    store: CuratedStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Scatter points behind one result, with the as-of value's source period and age."""
    return dashboard_queries.association_points(store, settings, objective, indicator, view, analysis_set)
