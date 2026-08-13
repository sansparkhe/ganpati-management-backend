"""Collection request/response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.enums import CollectionStatus, PaymentMethod
from app.schemas.common import (
    Money,
    PositiveMoney,
    TimestampedModel,
    TransactionDate,
    validate_transaction_date,
)
from app.schemas.flat import FlatContribution, FlatSummary


class CollectionCreate(BaseModel):
    flat_id: int = Field(gt=0, description="Must reference an existing flat")
    amount: PositiveMoney
    payment_method: PaymentMethod
    collected_on: TransactionDate | None = Field(
        default=None, description="Defaults to today when omitted"
    )
    status: CollectionStatus = CollectionStatus.CONFIRMED
    reference_no: str | None = Field(
        default=None, max_length=64, description="UPI txn id / cheque no / receipt no"
    )
    collected_by: str | None = Field(default=None, max_length=120)
    notes: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "flat_id": 1,
                "amount": 2500,
                "payment_method": "UPI",
                "collected_on": "2026-08-12",
                "reference_no": "UPI-8890123",
                "notes": "Ganpati contribution",
            }
        }
    )

    @field_validator("collected_on")
    @classmethod
    def _check_date(cls, value: date | None) -> date | None:
        return validate_transaction_date(value) if value is not None else None

    @field_validator("reference_no", "collected_by", "notes")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CollectionUpdate(BaseModel):
    """Partial update: only the fields you send are changed."""

    flat_id: int | None = Field(default=None, gt=0)
    amount: PositiveMoney | None = None
    payment_method: PaymentMethod | None = None
    collected_on: date | None = None
    status: CollectionStatus | None = None
    reference_no: str | None = Field(default=None, max_length=64)
    collected_by: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    audit_note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional reason for the change, stored in the audit log",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"amount": 3000, "audit_note": "Corrected receipt amount"}}
    )

    @field_validator("collected_on")
    @classmethod
    def _check_date(cls, value: date | None) -> date | None:
        return validate_transaction_date(value) if value is not None else None


class CollectionRead(TimestampedModel):
    id: int
    flat_id: int
    amount: Money
    payment_method: PaymentMethod
    status: CollectionStatus
    collected_on: date
    reference_no: str | None
    collected_by: str | None
    notes: str | None
    flat: FlatSummary

    @computed_field(description="Display friendly payment method, e.g. 'Bank Transfer'")
    @property
    def payment_method_label(self) -> str:
        return PaymentMethod(self.payment_method).label


class PaymentMethodTotal(BaseModel):
    payment_method: PaymentMethod
    label: str
    total: Money
    count: int


class WingTotal(BaseModel):
    wing: str
    total: Money
    count: int
    flats_total: int
    flats_contributed: int
    flats_pending: int


class StatusTotal(BaseModel):
    status: CollectionStatus
    total: Money
    count: int


class CollectionSummary(BaseModel):
    """GET /api/collections/summary"""

    total_collection: Money = Field(description="Sum of CONFIRMED collections only")
    pending_amount: Money = Field(description="Sum of PENDING (promised, not yet received)")
    cancelled_amount: Money
    collection_count: int = Field(description="Number of CONFIRMED transactions")
    total_flats: int
    flats_contributed: int
    flats_not_contributed: int
    contribution_percentage: float
    average_per_contributing_flat: Money
    highest_contribution: Money
    total_cash: Money
    total_upi: Money
    total_bank_transfer: Money
    total_other: Money
    by_payment_method: list[PaymentMethodTotal]
    by_status: list[StatusTotal]
    by_wing: list[WingTotal]
    by_flat: list[FlatContribution]


class PendingFlatsResponse(BaseModel):
    """Flats that have not contributed yet."""

    items: list[FlatSummary]
    total: int


class FlatContributionListResponse(BaseModel):
    items: list[FlatContribution]
    total: int


class FlatCollectionDetail(BaseModel):
    """GET /api/flats/{flat_id}/collections"""

    flat: FlatSummary
    total_amount: Money
    collection_count: int
    collections: list[CollectionRead]
