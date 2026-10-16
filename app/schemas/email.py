"""Request/response schemas for TBEMAIL."""

from __future__ import annotations

import re

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

_PHONE_RE = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean_phone(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = re.sub(r"[\s\-()]", "", value.strip())

    if not cleaned:
        return None

    if not _PHONE_RE.match(cleaned):
        raise ValueError(
            "phone_number must be a 10 digit Indian mobile number, optionally +91"
        )

    return cleaned


def _clean_email(value: str) -> str:
    cleaned = value.strip().lower()

    if not _EMAIL_RE.match(cleaned):
        raise ValueError("email_id must be a valid email address")

    return cleaned


def _check_dob(value: date | None) -> date | None:
    if value is not None and value >= date.today():
        raise ValueError("dob must be in the past")

    return value


def _clean_dob_str(value: str | None) -> str | None:
    """Validate a VARCHAR date_of_birth column while keeping it a str."""
    if value is None:
        return None

    cleaned = value.strip()

    if not cleaned:
        return None

    if not _ISO_DATE_RE.match(cleaned):
        raise ValueError("date_of_birth must be in YYYY-MM-DD format")

    try:
        parsed = date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError("date_of_birth must be a valid calendar date") from exc

    if parsed >= date.today():
        raise ValueError("date_of_birth must be in the past")

    return cleaned


def _clean_ts_str(value: str | None) -> str | None:
    """Validate a VARCHAR timestamp column while keeping it a str."""
    if value is None:
        return None

    cleaned = value.strip()

    if not cleaned:
        return None

    try:
        datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(
            "timestamp must be a valid ISO-8601 datetime string"
        ) from exc

    return cleaned


def _clean_is_online(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip().lower()

    if cleaned not in {"true", "false"}:
        raise ValueError("is_online must be 'true' or 'false'")

    return cleaned

# ---------------------------------------------------------------------------
# tbregmail
# ---------------------------------------------------------------------------


class RegMailCreate(BaseModel):
    phone_number: str = Field(
        max_length=20,
        examples=["9876543210"],
    )

    first_name: str = Field(
        min_length=1,
        max_length=160,
        examples=["Sunny"],
    )

    last_name: str = Field(
        min_length=1,
        max_length=160,
        examples=["Mane"],
    )

    email_id: str = Field(
        max_length=160,
        examples=["abc@gmail.com"],
    )

    date_of_birth: str | None = Field(
        default=None,
        max_length=10,
        examples=["1995-06-21"],
    )

    created_ts: str | None = Field(
        default=None,
        max_length=32,
        examples=["2026-09-26T10:30:00"],
    )

    completed_ts: str | None = Field(
        default=None,
        max_length=32,
    )

    _phone = field_validator("phone_number")(_clean_phone)

    _dob = field_validator("date_of_birth")(_clean_dob_str)

    _created_ts = field_validator("created_ts")(_clean_ts_str)

    _completed_ts = field_validator("completed_ts")(_clean_ts_str)


class RegMailUpdate(BaseModel):
    """Partial update — only the fields you send are changed."""

    phone_number: str | None = Field(
        default=None,
        max_length=20,
    )

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )

    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )

    date_of_birth: str | None = Field(
        default=None,
        max_length=10,
    )

    completed_ts: str | None = Field(
        default=None,
        max_length=32,
    )

    _phone = field_validator("phone_number")(_clean_phone)

    _dob = field_validator("date_of_birth")(_clean_dob_str)

    _completed_ts = field_validator("completed_ts")(_clean_ts_str)


class RegMailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    phone_number: str

    first_name: str

    last_name: str

    email_id: str

    date_of_birth: str | None

    created_ts: str

    completed_ts: str | None


# ---------------------------------------------------------------------------
# tbaprmail
# ---------------------------------------------------------------------------


class AprMailCreate(BaseModel):
    receiver_name: str = Field(
        min_length=1,
        max_length=160,
        examples=["Ravi Kulkarni"],
    )

    receiver_phone: str = Field(
        max_length=20,
        examples=["9876543210"],
    )

    is_online: str | None = Field(
        default=None,
        max_length=5,
        examples=["true"],
    )

    email_id: str = Field(
        max_length=160,
        examples=["abc@gmail.com"],
    )

    passcode: str | None = Field(
        default=None,
        min_length=6,
        max_length=20,
        examples=["123456"],
    )

    transaction_id: str = Field(
        min_length=1,
        max_length=160,
        examples=["TXN-2026-000123"],
    )

    expires_at: str | None  = Field(
        default=None,
        max_length=32,
        examples=["2026-09-26T10:30:00"],
    )   

    created_ts: str | None = Field(
        default=None,
        max_length=32,
        examples=["2026-09-26T10:30:00"],
    )

    completed_ts: str | None = Field(
        default=None,
        max_length=32,
    )

    _phone = field_validator("receiver_phone")(_clean_phone)

    _is_online = field_validator("is_online")(_clean_is_online)

    _created_ts = field_validator("created_ts")(_clean_ts_str)

    _completed_ts = field_validator("completed_ts")(_clean_ts_str)


class AprMailUpdate(BaseModel):
    """Partial update — only the fields you send are changed."""

    receiver_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )

    receiver_phone: str | None = Field(
        default=None,
        max_length=20,
    )

    is_online: str | None = Field(
        default=None,
        max_length=5,
    )

    transaction_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )

    completed_ts: str | None = Field(
        default=None,
        max_length=32,
    )

    _phone = field_validator("receiver_phone")(_clean_phone)

    _is_online = field_validator("is_online")(_clean_is_online)

    _completed_ts = field_validator("completed_ts")(_clean_ts_str)


class AprMailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    receiver_name: str

    receiver_phone: str

    email_id: str

    passcode: str

    is_online: str | None

    transaction_id: str

    expires_at: str

    created_ts: str

    completed_ts: str | None