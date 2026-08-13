"""Expense category schemas."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Money, TimestampedModel

_CODE_RE = re.compile(r"^[A-Z0-9_]{2,48}$")


def _slugify_code(value: str) -> str:
    code = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").upper()
    if not _CODE_RE.match(code):
        raise ValueError("code must be 2-48 characters of A-Z, 0-9 or underscore")
    return code


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80, examples=["Decoration"])
    code: str | None = Field(
        default=None,
        max_length=48,
        description="Machine key such as DECORATION. Derived from name when omitted.",
    )
    description: str | None = None
    is_active: bool = True
    sort_order: int = Field(default=100, ge=0)

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Generator Rent", "sort_order": 110}}
    )

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return _slugify_code(value) if value else None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return value.strip()


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    # `code` is intentionally immutable: it is the stable key Flutter filters on.


class ExpenseCategoryRead(TimestampedModel):
    id: int
    code: str
    name: str
    description: str | None
    is_active: bool
    sort_order: int
    is_system: bool


class ExpenseCategoryWithStats(ExpenseCategoryRead):
    expense_count: int = 0
    total_amount: Money = Field(default=0)


class CategoryListResponse(BaseModel):
    items: list[ExpenseCategoryRead]
    total: int
