"""Dashboard schema — everything the Flutter home screen needs in one call."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.collection import CollectionRead, PaymentMethodTotal, WingTotal
from app.schemas.common import Money
from app.schemas.expense import CategoryTotal, ExpenseRead


class FlatStats(BaseModel):
    total_flats: int
    active_flats: int
    flats_contributed: int
    flats_not_contributed: int
    collection_percentage: float = Field(description="flats_contributed / active_flats * 100")


class DashboardResponse(BaseModel):
    """GET /api/dashboard"""

    currency: str = "INR"
    currency_symbol: str = "₹"

    # --- headline numbers (the four cards on the home screen) ---
    total_collection: Money
    total_expenses: Money
    remaining_balance: Money
    pending_collection_amount: Money

    # --- flat participation ---
    total_flats: int
    active_flats: int
    flats_contributed: int
    flats_not_contributed: int
    collection_percentage: float = Field(description="Share of flats that paid, 0-100")
    expense_percentage: float = Field(description="Share of collected money already spent, 0-100")

    collection_count: int
    expense_count: int
    average_contribution: Money

    top_expense_categories: list[CategoryTotal]
    collection_by_payment_method: list[PaymentMethodTotal]
    collection_by_wing: list[WingTotal]

    recent_collections: list[CollectionRead]
    recent_expenses: list[ExpenseRead]

    flat_config_warning: str | None = Field(
        default=None,
        description="Set when the configured flat count differs from EXPECTED_TOTAL_FLATS",
    )
