"""Consistent API error types and response handlers."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """A safe, operator-facing API failure."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def install_error_handlers(app: FastAPI) -> None:
    """Register stable JSON error envelopes for API clients."""

    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for error in exc.errors():
            details.append({key: value for key, value in error.items() if key != "ctx"})
        return JSONResponse(
            status_code=422,
            content=error_payload("validation_error", "Request validation failed", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload("http_error", str(exc.detail)),
        )
