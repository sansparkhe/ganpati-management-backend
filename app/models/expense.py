"""Expense model — one row per spend transaction."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, MoneyType


class ExpenseCategory(str, Enum):
    """Spend categories.

    Subclasses `str` so FastAPI/Pydantic serialise it as a plain readable
    string ("DECORATION") rather than an enum wrapper.
    """

    DECORATION = "DECORATION"
    FOOD = "FOOD"
    SOUND = "SOUND"
    ELECTRICITY = "ELECTRICITY"
    POOJA = "POOJA"
    PRASAD = "PRASAD"
    CLEANING = "CLEANING"
    TRANSPORTATION = "TRANSPORTATION"
    ADVERTISEMENT = "ADVERTISEMENT"
    MISCELLANEOUS = "MISCELLANEOUS"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class Expense(Base):
    __tablename__ = "TBEXP"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    expense_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    expense_category: Mapped[ExpenseCategory] = mapped_column(
        # VARCHAR + CHECK rather than a native PG type, so adding a category is
        # an ordinary migration instead of an ALTER TYPE.
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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)

    # Credentials of whoever recorded the spend, as specified.
    username: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(128), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Expense id={self.id} name={self.expense_name!r} amount={self.amount}>"
