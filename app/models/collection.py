"""Request/response schemas for TBCOLL."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.expense import Money, PositiveMoney
import enum

class PaymentMode(str, enum.Enum):
    CASH = "CASH"
    UPI = "UPI"

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


class CollectionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120, examples=["Ramesh Patil"])
    amount: PositiveMoney
    payment_mode: PaymentMode = Field(examples=["UPI"])
    approver_name: str = Field(min_length=3, max_length=60, examples=["sunny"])
    approver_phone_number: str | None = Field(default=None, max_length=20, examples=["9876543210"])
    wing: str | None = Field(default=None, max_length=20, examples=["A1", "B2", "C2"])

    is_tenant: bool = Field(default=False, description="True when a tenant paid, not the owner")
    is_external: bool = Field(default=False, description="True when the payer is outside the society")
    tenant_name: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=20, examples=["9876543210"])
    transaction_id: str | None = Field(default=None, max_length=64, examples=["UPI-8890123"])
    receiver_name: str | None = Field(default=None, max_length=120)
    receiver_phone_number: str | None = Field(default=None, max_length=20, examples=["9876543210"])

    _phone = field_validator("phone_number", "receiver_phone_number", "approver_phone_number")(_clean_phone)

    @field_validator("name", "tenant_name", "transaction_id", "receiver_name", "approver_name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value else value

    @model_validator(mode="after")
    def _tenant_needs_name(self) -> CollectionCreate:
        # Mirrors the ck_TBCOLL_tenant_name_required_when_is_tenant constraint,
        # so the client gets a 422 instead of a database IntegrityError.
        if self.is_tenant and not self.tenant_name:
            raise ValueError("tenant_name is required when is_tenant is true")
        return self


class CollectionUpdate(BaseModel):
    """Partial update — only the fields you send are changed."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    amount: PositiveMoney | None = None
    payment_mode: PaymentMode | None = None
    approver_name: str | None = Field(default=None, min_length=3, max_length=60)
    approver_phone_number: str | None = Field(default=None, max_length=20)
    is_tenant: bool | None = None
    is_external: bool | None = None
    tenant_name: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=20)
    transaction_id: str | None = Field(default=None, max_length=64)
    receiver_name: str | None = Field(default=None, max_length=120)
    receiver_phone_number: str | None = Field(default=None, max_length=20)
    wing: str | None = Field(default=None, max_length=20)

    _phone = field_validator("phone_number", "receiver_phone_number", "approver_phone_number")(_clean_phone)


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_tenant: bool
    is_external: bool
    tenant_name: str | None
    phone_number: str | None
    amount: Money
    payment_mode: PaymentMode
    transaction_id: str | None
    receiver_name: str | None
    receiver_phone_number: str | None
    approver_name: str
    approver_phone_number: str | None
    wing: str | None