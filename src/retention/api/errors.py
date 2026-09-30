"""Turn errors into clear JSON responses with the right HTTP code (D-44).

Every error has the same shape, so the dashboard can show it without guessing:
    {"error": {"code": "not_found", "message": "unknown country 'FR' (known: ALL, GR, ...)"}}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from retention.domain.errors import DataNotBuiltError, InvalidFilterError, NotFoundError

log = logging.getLogger(__name__)


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=error_body("not_found", str(exc)))

    @app.exception_handler(InvalidFilterError)
    async def invalid_filter(request: Request, exc: InvalidFilterError) -> JSONResponse:
        return JSONResponse(status_code=400, content=error_body("invalid_filter", str(exc)))

    @app.exception_handler(RequestValidationError)
    async def invalid_parameter(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI would answer 422; D-44 uses 400 for any invalid filter, with a readable message.
        problems = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"] if part != "query")
            problems.append(f"{location}: {error['msg']}")
        return JSONResponse(status_code=400, content=error_body("invalid_filter", "; ".join(problems)))

    @app.exception_handler(DataNotBuiltError)
    async def not_built(request: Request, exc: DataNotBuiltError) -> JSONResponse:
        return JSONResponse(status_code=503, content=error_body("data_not_built", str(exc)))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback for us; never leak internals to the browser.
        log.exception("Unexpected error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "Unexpected server error; see the server log."),
        )
