from __future__ import annotations
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Boolean, Date, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.sql_loader import load
from app.utils.pdf_builder import build_ledger_pdf




router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
DbSession = Annotated[AsyncSession, Depends(get_db)]

from decimal import Decimal
from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_collections: Decimal
    total_expenses: Decimal
    balance: Decimal


_SELECT_COLLECTION_HISTORY = load("collections", "select_collections_history")
_SELECT_EXPENSES_HISTORY = load("expenses", "select_expenses_history")

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: DbSession):
    # Load the SQL query for fetching dashboard stats
    _DASHBOARD_STATS_QUERY = load("dashboard", "dashboard_stats")

    # Execute the query and fetch the results
    result = await db.execute(_DASHBOARD_STATS_QUERY)
    stats = result.fetchone()

    if stats is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dashboard stats not found")

    return dict(stats._mapping)


@router.get("/ledger_report/{year}")
async def ledger_report(year: int, db: DbSession):
    collections = (await db.execute(_SELECT_COLLECTION_HISTORY, {"year": year})).all()
    expenses = (await db.execute(_SELECT_EXPENSES_HISTORY, {"year": year})).all()

    if not collections and not expenses:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No ledger data found for year {year}"
        )

    pdf = await run_in_threadpool(build_ledger_pdf, year, collections, expenses)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ledger_{year}.pdf"'},
    )


