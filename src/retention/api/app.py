"""The FastAPI application: API under /api, dashboard files at / (D-05, D-44).

create_app()    -> builds the app: routers, error handlers and the dashboard files
                   (tests call it with their own settings)
retention serve -> runs it with uvicorn
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from retention.api.errors import register_error_handlers
from retention.api.routers import objectives, signals, system, trust
from retention.config import PROJECT_ROOT, Settings, load_settings
from retention.repository.curated_store import CuratedStore

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"


def create_app(settings: Settings | None = None, dashboard_dir: Path | None = DASHBOARD_DIR) -> FastAPI:
    if settings is None:
        settings = load_settings()

    app = FastAPI(
        title="Retention signals API",
        version="0.1.0",
        description=(
            "Workforce retention objectives next to external labour-market signals. "
            "Read-only; serves the curated data built by `retention run`. Interactive docs at /docs."
        ),
    )
    app.state.settings = settings
    app.state.store = CuratedStore(settings)

    register_error_handlers(app)
    app.include_router(system.router)
    app.include_router(objectives.router)
    app.include_router(signals.router)
    app.include_router(trust.router)

    # The dashboard (Step 7) is plain files. Mounted last, so /api/... routes always win.
    if dashboard_dir is not None and dashboard_dir.exists():
        app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    return app
