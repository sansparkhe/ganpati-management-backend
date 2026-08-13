"""Helpers for building the standard `{success, data, message}` envelope."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.schemas.common import ErrorResponse, PaginationMeta
from app.utils.pagination import PaginationParams, page_count


def envelope(data: Any, message: str = "OK") -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def paginated(
    items: Sequence[Any], total: int, pagination: PaginationParams, message: str = "OK"
) -> dict[str, Any]:
    pages = page_count(total, pagination.limit)
    meta = PaginationMeta(
        page=pagination.page,
        limit=pagination.limit,
        total=total,
        pages=pages,
        has_next=pagination.page < pages,
        has_previous=pagination.page > 1 and total > 0,
    )
    return envelope({"items": list(items), "pagination": meta}, message)


# Reusable OpenAPI response docs so Swagger shows the error shape too.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "Conflict with existing data"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}

NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Resource not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
