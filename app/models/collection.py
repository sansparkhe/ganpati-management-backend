"""Collection item model — one row per contribution received.

Each row is a standalone transaction: the contributor's details are recorded
on the row itself (owner/tenant name and phone) rather than through a link to
a flat register.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, String, false, true
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, MoneyType


class PaymentMode(str, Enum):
    """How the money moved.

    Subclasses `str` so FastAPI/Pydantic serialise it as a plain readable
    string ("UPI") rather than an enum wrapper.
    """

    CASH = "CASH"
    UPI = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"

    @property
    def label(self) -> str:
        return "UPI" if self is PaymentMode.UPI else self.value.replace("_", " ").title()


class CollectionItem(Base):
    __tablename__ = "TBCOLL"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        # A tenant payment must say who the tenant is. Written as `NOT is_tenant`
        # rather than `is_tenant = 0`, which PostgreSQL rejects (no boolean-to-
        # integer comparison); this form is valid on both PostgreSQL and SQLite.
        CheckConstraint(
            "NOT is_tenant OR tenant_name IS NOT NULL",
            name="tenant_name_required_when_is_tenant",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- workflow state ---
    approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false(), index=True
    )
    in_queue: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true(), index=True
    )

    # --- who paid ---
    owner_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    is_tenant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    tenant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- the money ---
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    payment_mode: Mapped[PaymentMode] = mapped_column(
        # VARCHAR + CHECK rather than a native PG type, so adding a mode is an
        # ordinary migration instead of an ALTER TYPE.
        SAEnum(
            PaymentMode,
            name="payment_mode",
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda cls: [member.value for member in cls],
        ),
        nullable=False,
        index=True,
    )
    # UPI/NEFT reference or cheque number; absent for cash.
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Volunteer physically holding the cash until it is banked.
    cash_held_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Credentials of whoever recorded the contribution, as specified.
    username: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(128), nullable=False)

    @property
    def paid_by(self) -> str:
        """Who the money actually came from."""
        return self.tenant_name if self.is_tenant and self.tenant_name else self.owner_name

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<CollectionItem id={self.id} owner={self.owner_name!r} amount={self.amount}>"
