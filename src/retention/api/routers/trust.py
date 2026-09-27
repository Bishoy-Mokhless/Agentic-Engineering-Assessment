"""GET /api/quality and GET /api/sources (the dashboard's Trust view)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from retention.api.dependencies import get_settings, get_store
from retention.config import Settings
from retention.repository.curated_store import CuratedStore
from retention.service import dashboard_queries

router = APIRouter(prefix="/api", tags=["trust"])


@router.get("/quality")
def quality(store: CuratedStore = Depends(get_store)) -> dict:
    """Reconciliation, flags and exclusions, coverage, flagged rows, and which run built each layer."""
    return dashboard_queries.quality(store)


@router.get("/sources")
def sources(store: CuratedStore = Depends(get_store), settings: Settings = Depends(get_settings)) -> dict:
    """Provider, dataset, licence, attribution, cadence, lag, freshness status and coverage per source."""
    return dashboard_queries.sources(store, settings)
