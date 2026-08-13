"""Collection (contribution) model.

Each row is ONE transaction. Totals are never stored — they are always
aggregated from these rows, so history stays editable and auditable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, MoneyType, TimestampMixin
from app.models.enums import CollectionStatus, PaymentMethod, string_enum

if TYPE_CHECKING:
    from app.models.flat import Flat


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_collections_flat_id", "flat_id"),
        Index("ix_collections_collected_on", "collected_on"),
        Index("ix_collections_payment_method", "payment_method"),
        Index("ix_collections_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # RESTRICT: a flat that has money recorded against it cannot be deleted,
    # which keeps the financial history consistent.
    flat_id: Mapped[int] = mapped_column(
        ForeignKey("flats.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        string_enum(PaymentMethod, "payment_method"), nullable=False
    )
    status: Mapped[CollectionStatus] = mapped_column(
        string_enum(CollectionStatus, "collection_status"),
        nullable=False,
        default=CollectionStatus.CONFIRMED,
        server_default=CollectionStatus.CONFIRMED.value,
    )
    # UPI txn id / cheque number / receipt number.
    reference_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    collected_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Volunteer who received the money.
    collected_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    flat: Mapped[Flat] = relationship(back_populates="collections", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Collection id={self.id} flat_id={self.flat_id} amount={self.amount}>"
