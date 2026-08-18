"""Request/response schemas for TBCOLL."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.collection import PaymentMode
from app.schemas.expense import Money, PositiveMoney

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
    owner_name: str = Field(min_length=2, max_length=120, examples=["Ramesh Patil"])
    amount: PositiveMoney
    payment_mode: PaymentMode = Field(examples=["UPI"])
    username: str = Field(min_length=3, max_length=60, examples=["sunny"])
    password: str = Field(min_length=1, max_length=128, description="Write-only")

    approved: bool = Field(default=False, description="Only approved money counts to totals")
    in_queue: bool = Field(default=True, description="Awaiting review")
    is_tenant: bool = Field(default=False, description="True when a tenant paid, not the owner")
    tenant_name: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=20, examples=["9876543210"])
    transaction_id: str | None = Field(default=None, max_length=64, examples=["UPI-8890123"])
    cash_held_by: str | None = Field(default=None, max_length=120)

    _phone = field_validator("phone_number")(_clean_phone)

    @field_validator("owner_name", "tenant_name", "transaction_id", "cash_held_by", "username")
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

    owner_name: str | None = Field(default=None, min_length=2, max_length=120)
    amount: PositiveMoney | None = None
    payment_mode: PaymentMode | None = None
    username: str | None = Field(default=None, min_length=3, max_length=60)
    password: str | None = Field(default=None, min_length=1, max_length=128)
    approved: bool | None = None
    in_queue: bool | None = None
    is_tenant: bool | None = None
    tenant_name: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=20)
    transaction_id: str | None = Field(default=None, max_length=64)
    cash_held_by: str | None = Field(default=None, max_length=120)

    _phone = field_validator("phone_number")(_clean_phone)


class CollectionRead(BaseModel):
    """`password` is deliberately absent — it is never returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    approved: bool
    in_queue: bool
    owner_name: str
    is_tenant: bool
    tenant_name: str | None
    phone_number: str | None
    amount: Money
    payment_mode: PaymentMode
    transaction_id: str | None
    cash_held_by: str | None
    username: str
    paid_by: str = Field(description="Tenant when is_tenant, otherwise the owner")
