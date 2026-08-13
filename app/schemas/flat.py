"""Flat request/response schemas."""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Money, ORMModel, TimestampedModel

_PHONE_RE = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")


def _clean_phone(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\s\-()]", "", value.strip())
    if not cleaned:
        return None
    if not _PHONE_RE.match(cleaned):
        raise ValueError(
            "phone must be a valid 10 digit Indian mobile number, optionally +91 prefixed"
        )
    return cleaned


class FlatBase(BaseModel):
    wing: str = Field(min_length=1, max_length=4, examples=["A"])
    flat_number: str = Field(min_length=1, max_length=16, examples=["A1"])
    display_name: str | None = Field(
        default=None, max_length=32, description="Defaults to flat_number when omitted"
    )
    owner_name: str | None = Field(default=None, max_length=120, examples=["Sunny Mane"])
    phone: str | None = Field(default=None, max_length=20, examples=["9876543210"])
    notes: str | None = None

    @field_validator("wing")
    @classmethod
    def _upper_wing(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("flat_number")
    @classmethod
    def _upper_flat_number(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("flat_number cannot be blank")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        return _clean_phone(value)

    @field_validator("owner_name", "display_name", "notes")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class FlatCreate(FlatBase):
    is_active: bool = True
    sort_order: int | None = Field(
        default=None, ge=0, description="Auto-derived from the flat number when omitted"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "wing": "A",
                "flat_number": "A13",
                "owner_name": "Ramesh Patil",
                "phone": "9876543210",
            }
        }
    )


class FlatBulkCreate(BaseModel):
    """Add several flats in one call — handy for the missing 24 -> 28 flats."""

    flats: list[FlatCreate] = Field(min_length=1, max_length=200)
    skip_existing: bool = Field(
        default=True,
        description="When true, existing flats are skipped instead of failing the request",
    )


class FlatUpdate(BaseModel):
    """All fields optional — only what you send is changed."""

    wing: str | None = Field(default=None, min_length=1, max_length=4)
    flat_number: str | None = Field(default=None, min_length=1, max_length=16)
    display_name: str | None = Field(default=None, max_length=32)
    owner_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("wing")
    @classmethod
    def _upper_wing(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @field_validator("flat_number")
    @classmethod
    def _upper_flat_number(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        return _clean_phone(value)


class FlatRead(TimestampedModel):
    id: int
    wing: str
    flat_number: str
    display_name: str
    owner_name: str | None
    phone: str | None
    notes: str | None
    is_active: bool
    sort_order: int


class FlatSummary(ORMModel):
    """Lightweight flat reference embedded in collection responses."""

    id: int
    wing: str
    flat_number: str
    display_name: str


class FlatListResponse(BaseModel):
    items: list[FlatRead]
    total: int
    wings: list[str]


class FlatBulkResult(BaseModel):
    created: list[FlatRead]
    skipped: list[str] = Field(description="Flat numbers that already existed")
    created_count: int
    skipped_count: int


class WingInfo(BaseModel):
    code: str
    configured_flat_count: int
    existing_flat_count: int


class FlatConfigResponse(BaseModel):
    """Surfaces the 24-vs-28 flat discrepancy instead of hiding it."""

    wings: list[WingInfo]
    configured_flat_count: int = Field(description="Total flats implied by SOCIETY_WINGS")
    existing_flat_count: int = Field(description="Flats actually present in the database")
    expected_total_flats: int = Field(description="EXPECTED_TOTAL_FLATS from the environment")
    matches_expectation: bool
    discrepancy: int = Field(description="expected_total_flats - configured_flat_count")
    message: str
    how_to_fix: list[str]


class FlatContribution(ORMModel):
    """Per-flat contribution row used by collection summaries."""

    flat_id: int
    wing: str
    flat_number: str
    display_name: str
    owner_name: str | None = None
    total_amount: Money
    collection_count: int
    has_contributed: bool
    last_collected_on: date | None = None
