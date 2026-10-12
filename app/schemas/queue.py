"""Request/response schemas for TBQUEUE."""

from __future__ import annotations

import re
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PHONE_RE = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")


def _clean_phone(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = re.sub(r"[\s\-()]", "", value.strip())

    if not cleaned:
        return None

    if not _PHONE_RE.match(cleaned):
        raise ValueError(
            "phone number must be a 10 digit Indian mobile number, optionally +91"
        )

    return cleaned


class QueueItemCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=160,
        examples=["Sunny Mane"],
    )

    phone_number: str | None = Field(
        default=None,
        max_length=20,
        examples=["9876543210"],
    )

    is_tenant: bool = Field(
        default=False,
        examples=[True],
    )

    wing: str = Field(
        min_length=1,
        max_length=20,
        examples=["A"],
    )

    is_external: bool = Field(
        default=False,
        examples=[False],
    )

    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        examples=["100.00"],
    )

    payment_mode: str = Field(
        min_length=1,
        max_length=50,
        examples=["cash"],
    )

    approver_name: str | None = Field(
        default=None,
        max_length=160,
        examples=["Admin"],
    )

    approver_phone_number: str | None = Field(
        default=None,
        max_length=20,
        examples=["9876543210"],
    )

    receiver_name: str | None = Field(
        default=None,
        max_length=160,
        examples=["Sunny Mane"],
    )

    receiver_phone_number: str | None = Field(
        default=None,
        max_length=20,
        examples=["9876543210"],
    )

    status: str = Field(
        default="pending",
        min_length=1,
        max_length=20,
        examples=["pending"],
    )

    _phones = field_validator(
        "phone_number",
        "approver_phone_number",
        "receiver_phone_number",
    )(_clean_phone)


class QueueItemUpdate(BaseModel):
    """Partial update — only the fields you send are changed."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )

    phone_number: str | None = Field(
        default=None,
        max_length=20,
    )

    is_tenant: bool | None = None

    wing: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )

    is_external: bool | None = None

    amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    payment_mode: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    approver_name: str | None = Field(
        default=None,
        max_length=160,
    )

    approver_phone_number: str | None = Field(
        default=None,
        max_length=20,
    )

    receiver_name: str | None = Field(
        default=None,
        max_length=160,
    )

    receiver_phone_number: str | None = Field(
        default=None,
        max_length=20,
    )

    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )

    _phones = field_validator(
        "phone_number",
        "approver_phone_number",
        "receiver_phone_number",
    )(_clean_phone)


class QueueItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    name: str

    phone_number: str | None

    is_tenant: bool

    wing: str

    is_external: bool

    amount: Decimal

    payment_mode: str

    approver_name: str | None

    approver_phone_number: str | None

    receiver_name: str | None

    receiver_phone_number: str | None

    status: str

class QueueApprove(BaseModel):
    """Body for approving a queue item. Only name and phone_number are needed."""

    name: str = Field(min_length=1, max_length=160, examples=["Ramesh Patil"])
    phone_number: str = Field(max_length=20, examples=["9123456780"])

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone_number")
    @classmethod
    def _phone_required(cls, value: str) -> str:
        cleaned = _clean_phone(value)
        if cleaned is None:
            raise ValueError("phone_number is required")
        return cleaned    