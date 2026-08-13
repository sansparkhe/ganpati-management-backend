"""Financial summary + dashboard aggregation.

Single source of truth for `remaining_balance`. Both /api/finance/summary and
/api/dashboard call `compute_totals()` so the two screens can never disagree.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import CollectionStatus
from app.schemas.collection import CollectionRead
from app.schemas.expense import ExpenseRead
from app.services import collection_service, expense_service, flat_service
from app.utils.money import ZERO, percentage, to_money


async def compute_totals(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> dict[str, Decimal | int]:
    """The three headline numbers, derived — never stored."""
    total_collection, collection_count = await collection_service.total_collected(
        db, status=CollectionStatus.CONFIRMED, date_from=date_from, date_to=date_to
    )
    total_expenses, expense_count = await expense_service.total_spent(
        db, date_from=date_from, date_to=date_to
    )
    return {
        "total_collection": total_collection,
        "total_expenses": total_expenses,
        "remaining_balance": to_money(total_collection - total_expenses),
        "collection_count": collection_count,
        "expense_count": expense_count,
    }


async def build_finance_summary(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> dict[str, Any]:
    totals = await compute_totals(db, date_from=date_from, date_to=date_to)
    pending_amount, _ = await collection_service.total_collected(
        db, status=CollectionStatus.PENDING, date_from=date_from, date_to=date_to
    )
    limit = settings.RECENT_ITEMS_LIMIT

    recent_collections = await collection_service.recent_collections(db, limit)
    recent_expenses = await expense_service.recent_expenses(db, limit)

    return {
        **totals,
        "currency": settings.CURRENCY_CODE,
        "currency_symbol": settings.CURRENCY_SYMBOL,
        "pending_collection_amount": pending_amount,
        "utilisation_percentage": percentage(totals["total_expenses"], totals["total_collection"]),
        "collection_by_payment_method": await collection_service.totals_by_payment_method(
            db, date_from=date_from, date_to=date_to
        ),
        "collection_by_wing": await collection_service.totals_by_wing(
            db, date_from=date_from, date_to=date_to
        ),
        "expenses_by_category": await expense_service.totals_by_category(
            db, date_from=date_from, date_to=date_to
        ),
        "expenses_by_payment_method": await expense_service.totals_by_payment_method(
            db, date_from=date_from, date_to=date_to
        ),
        "recent_collections": [CollectionRead.model_validate(row) for row in recent_collections],
        "recent_expenses": [ExpenseRead.model_validate(row) for row in recent_expenses],
    }


async def build_dashboard(db: AsyncSession) -> dict[str, Any]:
    """Everything the Flutter home screen needs, in one round trip."""
    totals = await compute_totals(db)
    pending_amount, _ = await collection_service.total_collected(
        db, status=CollectionStatus.PENDING
    )
    active_flats, contributed, not_contributed = await collection_service.flat_participation(db)

    total_flats = await flat_service.count_flats(db)

    limit = settings.RECENT_ITEMS_LIMIT
    recent_collections = await collection_service.recent_collections(db, limit)
    recent_expenses = await expense_service.recent_expenses(db, limit)

    average_contribution = (
        to_money(totals["total_collection"] / contributed) if contributed else ZERO
    )

    warning = None
    if not settings.flat_count_matches_expectation:
        warning = (
            f"{settings.configured_flat_count} flats are configured but "
            f"EXPECTED_TOTAL_FLATS is {settings.EXPECTED_TOTAL_FLATS}. "
            "See GET /api/flats/config."
        )

    return {
        "currency": settings.CURRENCY_CODE,
        "currency_symbol": settings.CURRENCY_SYMBOL,
        "total_collection": totals["total_collection"],
        "total_expenses": totals["total_expenses"],
        "remaining_balance": totals["remaining_balance"],
        "pending_collection_amount": pending_amount,
        "total_flats": total_flats,
        "active_flats": active_flats,
        "flats_contributed": contributed,
        "flats_not_contributed": not_contributed,
        "collection_percentage": percentage(contributed, active_flats),
        "expense_percentage": percentage(totals["total_expenses"], totals["total_collection"]),
        "collection_count": totals["collection_count"],
        "expense_count": totals["expense_count"],
        "average_contribution": average_contribution,
        "top_expense_categories": await expense_service.totals_by_category(db, limit=5),
        "collection_by_payment_method": await collection_service.totals_by_payment_method(db),
        "collection_by_wing": await collection_service.totals_by_wing(db),
        "recent_collections": [CollectionRead.model_validate(row) for row in recent_collections],
        "recent_expenses": [ExpenseRead.model_validate(row) for row in recent_expenses],
        "flat_config_warning": warning,
    }
