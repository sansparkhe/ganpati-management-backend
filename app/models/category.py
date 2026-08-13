"""Expense category model.

Categories live in a table (not a hard-coded enum) so they can be managed
through the API without a code change — requirement #6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.expense import Expense


class ExpenseCategory(Base, TimestampMixin):
    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_expense_categories_code"),
        UniqueConstraint("name", name="uq_expense_categories_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable machine key used by the API filters, e.g. "DECORATION".
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    # Human readable label shown in the Flutter UI, e.g. "Decoration".
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Seeded defaults are flagged so the UI can discourage renaming them.
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    expenses: Mapped[list[Expense]] = relationship(
        back_populates="category",
        passive_deletes=True,
        lazy="raise",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<ExpenseCategory id={self.id} code={self.code!r}>"
