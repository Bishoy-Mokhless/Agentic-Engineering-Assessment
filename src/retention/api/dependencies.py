"""Dependency injection for the routers.

Spring analogy: constructor injection / @Autowired. FastAPI calls these functions for each
request (via Depends) and passes the result into the endpoint function.
"""

from __future__ import annotations

from fastapi import Query, Request

from retention.config import Settings
from retention.repository.curated_store import CuratedStore


def get_store(request: Request) -> CuratedStore:
    return request.app.state.store


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def year_query(description: str):
    """Optional year filter (2000-2100). Create a NEW Query object per parameter: sharing one
    Query between year_from and year_to made FastAPI treat them as one parameter
    (year_to silently took year_from's value; found while testing Step 6)."""
    return Query(default=None, ge=2000, le=2100, description=description)
