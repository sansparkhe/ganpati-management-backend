"""Financial summary endpoints — /api/finance"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.dependencies import DbSession
from app.schemas.common import APIResponse
from app.schemas.finance import FinanceSummary, FinanceTotals
from app.services import finance_service
from app.utils.responses import ERROR_RESPONSES, envelope

router = APIRouter(prefix="/finance", tags=["Finance"], responses=ERROR_RESPONSES)


@router.get(
    "/summary",
    response_model=APIResponse[FinanceSummary],
    summary="Total collection, total expenses and remaining balance",
    description=(
        "`remaining_balance` = `total_collection` - `total_expenses`, calculated "
        "from the transaction rows on every request. It is never stored, so it "
        "can never drift out of sync."
    ),
)
async def finance_summary(
    db: DbSession,
    date_from: date | None = Query(None, description="Inclusive lower bound on transaction dates"),
    date_to: date | None = Query(None, description="Inclusive upper bound on transaction dates"),
) -> dict:
    summary = await finance_service.build_finance_summary(db, date_from=date_from, date_to=date_to)
    return envelope(FinanceSummary(**summary), "Financial summary generated successfully")


@router.get(
    "/balance",
    response_model=APIResponse[FinanceTotals],
    summary="Just the three headline numbers",
    description="Lightweight version of /finance/summary for a compact widget.",
)
async def finance_balance(db: DbSession) -> dict:
    totals = await finance_service.compute_totals(db)
    return envelope(
        FinanceTotals(
            total_collection=totals["total_collection"],
            total_expenses=totals["total_expenses"],
            remaining_balance=totals["remaining_balance"],
        ),
        "Balance calculated successfully",
    )
