from __future__ import annotations
from decimal import Decimal
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import Numeric, String, bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.expense import Expense, ExpenseCategory
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.sql_loader import load

router = APIRouter(prefix="/expenses", tags=["Expenses"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
_MONEY = Numeric(12, 2, asdecimal=True)


_SELECT_EXPENSES = (
    load("expenses", "select_expenses")
)

_TOTAL_EXPENSES = load("expenses", "total_expenses")   
_INSERT_EXPENSE = load("expenses", "insert_expense")
_SELECT_EXPENSE_BY_ID = load("expenses", "select_by_id")


def _row_to_read(row):
    return ExpenseRead.model_validate(dict(row._mapping))


async def _get_orm_or_404(db, expense_id):
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Expense {expense_id} does not exist")
    return expense


@router.post("/create", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreate, db: DbSession):
    params = payload.model_dump()
    params["expense_category"] = payload.expense_category.value
    result = await db.execute(_INSERT_EXPENSE, params)
    inserted_id = result.lastrowid 
    await db.commit()
    row = (await db.execute(_SELECT_EXPENSE_BY_ID, {"id": inserted_id})).one()
    return _row_to_read(row)


@router.get("", response_model=list[ExpenseRead])
async def list_expenses(
    db: DbSession,
    response: Response,
    expense_category: ExpenseCategory | None = Query(None),
    username: str | None = Query(None),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    search: str | None = Query(None, min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    params = {
        "expense_category": expense_category.value if expense_category else None,
        "username": username.strip() if username else None,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "search": f"%{search.strip()}%" if search else None,
        "limit": limit,
        "skip": skip,
    }
    rows = (await db.execute(_SELECT_EXPENSES, params)).all()
    return [_row_to_read(row) for row in rows]


@router.get("/total")
async def expense_total(db: DbSession):
    totals = (await db.execute(_TOTAL_EXPENSES)).one()._mapping
    return {
        "total_expenses": float(totals["total_expense"]),
        "expense_count": 0,  
        "average_expense": 0,  
        "highest_expense": 0  
    }





