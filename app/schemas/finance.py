"""Financial summary schemas.

`remaining_balance` is ALWAYS derived: total_collection - total_expenses.
It is never stored in, or read from, a column.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.collection import CollectionRead, PaymentMethodTotal, WingTotal
from app.schemas.common import Money
from app.schemas.expense import CategoryTotal, ExpenseRead


class FinanceTotals(BaseModel):
    total_collection: Money
    total_expenses: Money
    remaining_balance: Money = Field(
        description="Calculated as total_collection - total_expenses; never stored"
    )


class FinanceSummary(FinanceTotals):
    """GET /api/finance/summary"""

    currency: str = "INR"
    currency_symbol: str = "₹"

    collection_count: int
    expense_count: int
    pending_collection_amount: Money

    utilisation_percentage: float = Field(
        description="Percentage of collected money already spent, 0-100"
    )

    collection_by_payment_method: list[PaymentMethodTotal]
    collection_by_wing: list[WingTotal]
    expenses_by_category: list[CategoryTotal]
    expenses_by_payment_method: list[PaymentMethodTotal]

    recent_collections: list[CollectionRead]
    recent_expenses: list[ExpenseRead]
