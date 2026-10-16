"""Request/response schemas for TBWHAT."""

from __future__ import annotations

import re

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PHONE_RE = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")


def _clean_phone(value: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", value.strip())

    if not cleaned:
        raise ValueError("phone_number is required")

    if not _PHONE_RE.match(cleaned):
        raise ValueError(
            "phone_number must be a 10 digit Indian mobile number, optionally +91"
        )

    return cleaned


class WhatsAppJobCreate(BaseModel):
    phone_number: str = Field(
        max_length=20,
        examples=["9876543210"],
    )

    name: str = Field(
        min_length=1,
        max_length=160,
        examples=["Sunny Mane"],
    )

    created_at: datetime | None = None

    completed_at: datetime | None = None

    _phone = field_validator("phone_number")(_clean_phone)


class WhatsAppJobUpdate(BaseModel):
    """Partial update — only the fields you send are changed."""

    phone_number: str | None = Field(
        default=None,
        max_length=20,
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )

    completed_at: datetime | None = None

    _phone = field_validator("phone_number")(_clean_phone)


class WhatsAppJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    phone_number: str

    name: str

    created_at: datetime

    completed_at: datetime | None
