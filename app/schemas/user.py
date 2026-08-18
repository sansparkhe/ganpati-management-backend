"""Request/response schemas for TBUSER."""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")


def _clean_phone(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\s\-()]", "", value.strip())
    if not cleaned:
        return None
    if not _PHONE_RE.match(cleaned):
        raise ValueError("phone_number must be a 10 digit Indian mobile number, optionally +91")
    return cleaned


def _clean_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise ValueError("email_id must be a valid email address")
    return cleaned


def _check_dob(value: date | None) -> date | None:
    if value is not None and value >= date.today():
        raise ValueError("dob must be in the past")
    return value


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80, examples=["Sunny"])
    last_name: str = Field(min_length=1, max_length=80, examples=["Mane"])
    email_id: str = Field(max_length=160, examples=["sunny.mane@example.com"])
    phone_number: str | None = Field(default=None, max_length=20, examples=["9876543210"])
    dob: date | None = Field(default=None, description="Date of birth, YYYY-MM-DD")
    admin_access: bool = False

    _phone = field_validator("phone_number")(_clean_phone)
    _email = field_validator("email_id")(_clean_email)
    _dob = field_validator("dob")(_check_dob)


class UserUpdate(BaseModel):
    """Partial update — only the fields you send are changed."""

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    email_id: str | None = Field(default=None, max_length=160)
    phone_number: str | None = Field(default=None, max_length=20)
    dob: date | None = None
    admin_access: bool | None = None

    _phone = field_validator("phone_number")(_clean_phone)
    _email = field_validator("email_id")(_clean_email)
    _dob = field_validator("dob")(_check_dob)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    full_name: str
    phone_number: str | None
    dob: date | None
    email_id: str
    admin_access: bool
