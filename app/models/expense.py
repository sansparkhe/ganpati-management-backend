"""Expense model — one row per spend transaction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, MoneyType, TimestampMixin
from app.models.enums import PaymentMethod, string_enum

if TYPE_CHECKING:
    from app.models.category import ExpenseCategory


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_expenses_category_id", "category_id"),
        Index("ix_expenses_spent_on", "spent_on"),
        Index("ix_expenses_payment_method", "payment_method"),
        Index("ix_expenses_title", "title"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # RESTRICT: a category still referenced by expenses cannot be deleted.
    category_id: Mapped[int] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        string_enum(PaymentMethod, "payment_method"), nullable=False
    )
    spent_on: Mapped[date] = mapped_column(Date, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Bill number / UPI txn id / receipt reference.
    reference_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Committee member who actually paid.
    paid_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[ExpenseCategory] = relationship(back_populates="expenses", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Expense id={self.id} title={self.title!r} amount={self.amount}>"
