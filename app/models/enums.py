"""Enumerations shared by models and schemas.

They subclass `str` so FastAPI/Pydantic serialise them as plain readable
strings ("UPI", "CONFIRMED") — exactly what the Flutter app receives.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


class PaymentMethod(str, Enum):
    CASH = "CASH"
    UPI = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"
    OTHER = "OTHER"

    @property
    def label(self) -> str:
        return _PAYMENT_METHOD_LABELS[self]


_PAYMENT_METHOD_LABELS: dict[PaymentMethod, str] = {
    PaymentMethod.CASH: "Cash",
    PaymentMethod.UPI: "UPI",
    PaymentMethod.BANK_TRANSFER: "Bank Transfer",
    PaymentMethod.OTHER: "Other",
}


class CollectionStatus(str, Enum):
    """Lifecycle of a contribution.

    CONFIRMED — money actually received. This is the default and the ONLY
                status counted in totals / remaining balance.
    PENDING   — promised but not yet received; reported separately.
    CANCELLED — recorded by mistake or refunded; excluded from every total.
    """

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditEntity(str, Enum):
    FLAT = "FLAT"
    COLLECTION = "COLLECTION"
    EXPENSE = "EXPENSE"
    EXPENSE_CATEGORY = "EXPENSE_CATEGORY"


def string_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Store an enum as VARCHAR + CHECK constraint rather than a native PG type.

    Adding a new payment method then becomes an ordinary migration instead of
    an `ALTER TYPE`, and the same models work on SQLite for the test suite.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )
