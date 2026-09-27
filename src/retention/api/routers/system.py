"""GET /api/health and GET /api/filters."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from retention.api.dependencies import get_settings, get_store
from retention.config import Settings
from retention.repository.curated_store import CuratedStore
from retention.service import dashboard_queries

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(store: CuratedStore = Depends(get_store), settings: Settings = Depends(get_settings)) -> dict:
    """Is the data built, which run built it, and is any source stale? Always 200 (status inside)."""
    return dashboard_queries.health(store, settings)


@router.get("/filters")
def filters(store: CuratedStore = Depends(get_store), settings: Settings = Depends(get_settings)) -> dict:
    """Values for the dashboard dropdowns: countries, objectives, segments, periods, indicators."""
    return dashboard_queries.filters(store, settings)
