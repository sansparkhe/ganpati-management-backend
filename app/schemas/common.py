"""Shared schema building blocks: the response envelope, money and date types."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.core.config import settings

T = TypeVar("T")


# ---------------------------------------------------------------- money ----
# Stored and computed as Decimal; emitted to JSON as a plain number so the
# Flutter side receives `2500.0` (a `double`) rather than the string "2500.00".
_json_number = PlainSerializer(lambda v: float(v), return_type=float, when_used="json")

Money = Annotated[
    Decimal,
    Field(max_digits=12, decimal_places=2),
    _json_number,
]
PositiveMoney = Annotated[
    Decimal,
    Field(gt=0, max_digits=12, decimal_places=2, description="Must be greater than 0"),
    _json_number,
]


# ----------------------------------------------------------------- date ----
def validate_transaction_date(value: date) -> date:
    """Shared date rule for collections and expenses."""
    if not settings.ALLOW_FUTURE_DATES and value > date.today():
        raise ValueError("date cannot be in the future")
    if value.year < 2000:
        raise ValueError("date is unrealistically old (year must be >= 2000)")
    return value


TransactionDate = Annotated[
    date,
    Field(description="ISO date, e.g. 2026-08-12. Future dates are rejected by default."),
]


# ------------------------------------------------------------- envelope ----
class APIResponse(BaseModel, Generic[T]):
    """The single response shape used by every successful endpoint."""

    success: bool = True
    data: T | None = None
    message: str = "OK"


class ErrorResponse(BaseModel):
    """The single response shape used by every failure."""

    success: bool = False
    message: str = Field(description="Human readable message, safe to show in the UI")
    error: str = Field(description="Stable machine readable code, e.g. FLAT_NOT_FOUND")
    details: Any | None = Field(
        default=None, description="Optional extra context (e.g. field level errors)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "message": "Flat A5 does not exist",
                "error": "FLAT_NOT_FOUND",
                "details": None,
            }
        }
    )


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
    has_next: bool
    has_previous: bool


class Page(BaseModel, Generic[T]):
    """Envelope `data` payload for paginated list endpoints."""

    items: list[T]
    pagination: PaginationMeta


class ORMModel(BaseModel):
    """Base for every schema built from a SQLAlchemy row."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedModel(ORMModel):
    created_at: datetime
    updated_at: datetime


class DeletedResponse(BaseModel):
    id: int
    deleted: bool = True
