"""The standard response envelope every endpoint can return.

Unlike its three neighbours in this package, this module holds no SQLAlchemy
table — it is a Pydantic shape describing the JSON wrapper around a payload.
It lives here because the envelope is part of the API's data model.

    {
      "code": 200,
      "message": "User fetched successfully",
      "response": { "id": 1, ... },
      "success": true,
      "error": null,
      "timestamp": "2026-08-16T01:20:00Z"
    }

`APIResponse` is generic, so `response` keeps its real type in OpenAPI:

    @router.get("/{user_id}", response_model=APIResponse[UserRead])
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class APIResponse(BaseModel, Generic[T]):
    """One envelope for every successful reply."""

    code: int = Field(default=200, description="HTTP status code, mirrored in the body")
    message: str = Field(default="OK", description="Human readable, safe to show in the UI")
    response: T | None = Field(default=None, description="The actual payload; null on failure")

    # --- added beyond the requested three ---
    success: bool = Field(default=True, description="Lets a client branch without reading `code`")
    error: str | None = Field(
        default=None,
        description="Stable machine readable code (e.g. USER_NOT_FOUND); null when success",
    )
    timestamp: datetime = Field(default_factory=_utcnow, description="When the reply was built")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 200,
                "message": "Users fetched successfully",
                "response": [{"id": 1, "first_name": "Sunny", "last_name": "Mane"}],
                "success": True,
                "error": None,
                "timestamp": "2026-08-16T01:20:00Z",
            }
        }
    )

    # ------------------------------------------------------------ builders --
    @classmethod
    def ok(cls, response: T | None = None, message: str = "OK") -> APIResponse[T]:
        return cls(code=200, message=message, response=response)

    @classmethod
    def created(cls, response: T | None = None, message: str = "Created") -> APIResponse[T]:
        return cls(code=201, message=message, response=response)

    @classmethod
    def fail(cls, message: str, *, code: int = 400, error: str = "BAD_REQUEST") -> APIResponse[T]:
        """Failure carries no payload, so `response` stays null."""
        return cls(code=code, message=message, response=None, success=False, error=error)


class PageInfo(BaseModel):
    """Pagination block for list endpoints."""

    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    total: int = Field(ge=0, description="Rows matching the query, ignoring pagination")
    pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool

    @classmethod
    def build(cls, *, page: int, limit: int, total: int) -> PageInfo:
        pages = -(-total // limit) if limit > 0 and total else 0
        return cls(
            page=page,
            limit=limit,
            total=total,
            pages=pages,
            has_next=page < pages,
            has_previous=page > 1 and total > 0,
        )


class PaginatedResponse(APIResponse[list[T]], Generic[T]):
    """`APIResponse` whose payload is a list, plus the page metadata."""

    pagination: PageInfo | None = None

    @classmethod
    def of(
        cls,
        items: list[T],
        *,
        page: int,
        limit: int,
        total: int,
        message: str = "OK",
    ) -> PaginatedResponse[T]:
        return cls(
            code=200,
            message=message,
            response=items,
            pagination=PageInfo.build(page=page, limit=limit, total=total),
        )
