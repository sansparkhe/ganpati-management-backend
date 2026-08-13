"""Metadata schema.

`GET /api/meta` gives the Flutter app every dropdown value in a single call:
payment methods, statuses, wings and active expense categories.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.category import ExpenseCategoryRead


class EnumOption(BaseModel):
    value: str
    label: str


class MetaResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    currency: str
    currency_symbol: str
    payment_methods: list[EnumOption]
    collection_statuses: list[EnumOption]
    wings: list[str]
    expense_categories: list[ExpenseCategoryRead]
    default_page_size: int
    max_page_size: int


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str
    version: str
