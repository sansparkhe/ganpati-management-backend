"""Global exception handlers.

Every failure leaves the API in the same shape:

    {"success": false, "message": "...", "error": "CODE", "details": ...}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger("ganpati.errors")

# Maps generic HTTP status codes to stable error codes.
_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
}


def _error_response(
    *, status_code: int, message: str, error: str, details: object = None
) -> JSONResponse:
    payload = {"success": False, "message": message, "error": error, "details": details}
    return JSONResponse(status_code=status_code, content=payload)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            message=exc.message,
            error=exc.error_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        first = details[0] if details else None
        message = f"{first['field']}: {first['message']}" if first else "Request validation failed"
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=message,
            error="VALIDATION_ERROR",
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            message=str(exc.detail),
            error=_STATUS_CODES.get(exc.status_code, "HTTP_ERROR"),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error: %s", exc)
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            message="The request violates a database constraint (duplicate or missing reference).",
            error="INTEGRITY_ERROR",
            details=str(exc.orig) if settings.DEBUG else None,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_db_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="A database error occurred.",
            error="DATABASE_ERROR",
            details=str(exc) if settings.DEBUG else None,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Something went wrong. Please try again.",
            error="INTERNAL_ERROR",
            details=repr(exc) if settings.DEBUG else None,
        )
