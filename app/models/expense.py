from __future__ import annotations

from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, MoneyType


class ExpenseCategory(str, Enum):
    DECORATION = "DECORATION"
    FOOD = "FOOD"
    SOUND = "SOUND"
    ELECTRICITY = "ELECTRICITY"
    POOJA = "POOJA"
    PRASAD = "PRASAD"
    CLEANING = "CLEANING"
    TRANSPORT = "TRANSPORT"
    ADVERTISEMENT = "ADVERTISEMENT"
    MISCELLANEOUS = "MISCELLANEOUS"


class Expense(Base):
    __tablename__ = "tbexp"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="amount_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    expense_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        index=True,
    )

    expense_category: Mapped[ExpenseCategory] = mapped_column(
        SAEnum(
            ExpenseCategory,
            name="expense_category",
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda cls: [member.value for member in cls],
        ),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        MoneyType,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )

    phone_number: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    def __repr__(self):
        return (
            f"<Expense "
            f"id={self.id} "
            f"name={self.expense_name!r} "
            f"amount={self.amount}>"
        )