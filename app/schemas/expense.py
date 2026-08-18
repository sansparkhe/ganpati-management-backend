"""Request/response schemas for TBEXP."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from app.models.expense import ExpenseCategory

# Decimal everywhere internally; emitted to JSON as a plain number so Flutter
# receives `3500.0` rather than the string "3500.00".
_as_number = PlainSerializer(lambda v: float(v), return_type=float, when_used="json")
Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2), _as_number]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2), _as_number]


class ExpenseCreate(BaseModel):
    expense_name: str = Field(min_length=2, max_length=160, examples=["Decoration material"])
    expense_category: ExpenseCategory = Field(examples=["DECORATION"])
    amount: PositiveMoney
    username: str = Field(min_length=3, max_length=60, examples=["sunny"])
    password: str = Field(min_length=1, max_length=128, description="Write-only")
    description: str | None = Field(default=None, examples=["Sai Decorators, bill BILL-104"])

    @field_validator("expense_name", "username")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value else None


class ExpenseUpdate(BaseModel):
    """Partial update — only the fields you send are changed."""

    expense_name: str | None = Field(default=None, min_length=2, max_length=160)
    expense_category: ExpenseCategory | None = None
    amount: PositiveMoney | None = None
    description: str | None = None
    username: str | None = Field(default=None, min_length=3, max_length=60)
    password: str | None = Field(default=None, min_length=1, max_length=128)


class ExpenseRead(BaseModel):
    """`password` is deliberately absent — it is never returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_name: str
    expense_category: ExpenseCategory
    description: str | None
    amount: Money
    username: str
