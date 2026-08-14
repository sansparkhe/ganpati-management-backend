"""Expense request/response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.models.enums import PaymentMethod
from app.schemas.category import ExpenseCategoryRead
from app.schemas.collection import PaymentMethodTotal
from app.schemas.common import (
    Money,
    PositiveMoney,
    TimestampedModel,
    TransactionDate,
    validate_transaction_date,
)


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160, examples=["Decoration material"])
    amount: PositiveMoney
    payment_method: PaymentMethod
    # Send either category_id or category_code — whichever is easier in Flutter.
    category_id: int | None = Field(default=None, gt=0)
    category_code: str | None = Field(default=None, max_length=48, examples=["DECORATION"])
    spent_on: TransactionDate | None = Field(
        default=None, description="Defaults to today when omitted"
    )
    description: str | None = None
    vendor: str | None = Field(default=None, max_length=160, examples=["Sai Decorators"])
    reference_no: str | None = Field(default=None, max_length=64, description="Bill / txn number")
    paid_by: str | None = Field(default=None, max_length=120)
    notes: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Decoration material",
                "amount": 3500,
                "payment_method": "UPI",
                "category_code": "DECORATION",
                "spent_on": "2026-08-12",
                "vendor": "Sai Decorators",
                "reference_no": "BILL-104",
            }
        }
    )

    @field_validator("spent_on")
    @classmethod
    def _check_date(cls, value: date | None) -> date | None:
        return validate_transaction_date(value) if value is not None else None

    @field_validator("category_code")
    @classmethod
    def _upper_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _require_a_category(self) -> ExpenseCreate:
        # Omitting both is a client mistake (422), not a missing resource (404).
        if self.category_id is None and self.category_code is None:
            raise ValueError("either category_id or category_code is required")
        return self


class ExpenseUpdate(BaseModel):
    """Partial update: only the fields you send are changed."""

    title: str | None = Field(default=None, min_length=2, max_length=160)
    amount: PositiveMoney | None = None
    payment_method: PaymentMethod | None = None
    category_id: int | None = Field(default=None, gt=0)
    category_code: str | None = Field(default=None, max_length=48)
    spent_on: date | None = None
    description: str | None = None
    vendor: str | None = Field(default=None, max_length=160)
    reference_no: str | None = Field(default=None, max_length=64)
    paid_by: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    audit_note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional reason for the change, stored in the audit log",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"amount": 3500, "audit_note": "Vendor revised the bill"}}
    )

    @field_validator("spent_on")
    @classmethod
    def _check_date(cls, value: date | None) -> date | None:
        return validate_transaction_date(value) if value is not None else None

    @field_validator("category_code")
    @classmethod
    def _upper_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class ExpenseRead(TimestampedModel):
    id: int
    title: str
    description: str | None
    amount: Money
    payment_method: PaymentMethod
    category_id: int
    spent_on: date
    vendor: str | None
    reference_no: str | None
    paid_by: str | None
    notes: str | None
    category: ExpenseCategoryRead

    @computed_field(description="Display friendly payment method, e.g. 'Bank Transfer'")
    @property
    def payment_method_label(self) -> str:
        return PaymentMethod(self.payment_method).label

    @computed_field(description="Shortcut for category.code, convenient for list UIs")
    @property
    def category_code(self) -> str:
        return self.category.code

    @computed_field(description="Shortcut for category.name")
    @property
    def category_name(self) -> str:
        return self.category.name


class CategoryTotal(BaseModel):
    category_id: int
    category_code: str
    category_name: str
    total: Money
    count: int
    percentage: float = Field(description="Share of total expenses, 0-100")


class ExpenseSummary(BaseModel):
    """GET /api/expenses/summary"""

    total_expenses: Money
    expense_count: int
    average_expense: Money
    highest_expense: Money
    total_cash: Money
    total_upi: Money
    total_bank_transfer: Money
    total_other: Money
    by_category: list[CategoryTotal]
    by_payment_method: list[PaymentMethodTotal]
