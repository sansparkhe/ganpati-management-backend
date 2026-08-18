"""Expense endpoints — /api/expenses (table TBEXP).

Inserts and reads run the statements stored in `sql/queries/expenses.sql`; the
partial update and delete stay on the ORM, because a PATCH-style update needs
a SET clause built from whichever fields the client actually sent, which a
static .sql file cannot express.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import Numeric, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.expense import Expense, ExpenseCategory
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.sql_loader import load

router = APIRouter(prefix="/expenses", tags=["Expenses"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_MONEY = Numeric(12, 2, asdecimal=True)

# Money is a Decimal, which the raw sqlite3 driver cannot bind or return on its
# own; typing the parameters and the result column keeps it exact end to end.
_INSERT_EXPENSE = load("expenses", "insert_expense").bindparams(bindparam("amount", type_=_MONEY))
_SELECT_EXPENSES = (
    load("expenses", "select_expenses")
    .bindparams(bindparam("min_amount", type_=_MONEY), bindparam("max_amount", type_=_MONEY))
    .columns(amount=_MONEY)
)
_COUNT_EXPENSES = load("expenses", "count_expenses").bindparams(
    bindparam("min_amount", type_=_MONEY), bindparam("max_amount", type_=_MONEY)
)
_SELECT_EXPENSE_BY_ID = load("expenses", "select_expense_by_id").columns(amount=_MONEY)
_EXPENSE_TOTALS = load("expenses", "expense_totals")
_EXPENSE_TOTALS_BY_CATEGORY = load("expenses", "expense_totals_by_category")


def _row_to_read(row: Any) -> ExpenseRead:
    return ExpenseRead.model_validate(dict(row._mapping))


async def _get_orm_or_404(db: AsyncSession, expense_id: int) -> Expense:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Expense {expense_id} does not exist")
    return expense


# --------------------------------------------------------------- create ----
@router.post(
    "",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an expense row to TBEXP",
    description="Runs the `insert_expense` statement from sql/queries/expenses.sql.",
)
async def create_expense(payload: ExpenseCreate, db: DbSession) -> ExpenseRead:
    params = payload.model_dump()
    params["expense_category"] = payload.expense_category.value
    row = (await db.execute(_INSERT_EXPENSE, params)).one()
    await db.commit()
    return _row_to_read(row)


# ----------------------------------------------------------- retrieval ----
@router.get(
    "",
    response_model=list[ExpenseRead],
    summary="List expenses",
    description=(
        "Runs `select_expenses` / `count_expenses` from sql/queries/expenses.sql. "
        "The unpaginated match count is returned in the `X-Total-Count` header."
    ),
)
async def list_expenses(
    db: DbSession,
    response: Response,
    expense_category: ExpenseCategory | None = Query(None),
    username: str | None = Query(None, description="Only rows recorded by this user"),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    search: str | None = Query(None, min_length=1, description="Matches name or description"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[ExpenseRead]:
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
    total = (await db.execute(_COUNT_EXPENSES, params)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    return [_row_to_read(row) for row in rows]


@router.get(
    "/total",
    summary="Total spent, overall and per category",
    description=(
        "Runs `expense_totals` and `expense_totals_by_category` from sql/queries/expenses.sql."
    ),
)
async def expense_total(db: DbSession) -> dict:
    totals = (await db.execute(_EXPENSE_TOTALS)).one()._mapping
    rows = (await db.execute(_EXPENSE_TOTALS_BY_CATEGORY)).all()
    return {
        "total_expenses": float(totals["total_expenses"]),
        "expense_count": totals["expense_count"],
        "average_expense": round(float(totals["average_expense"]), 2),
        "highest_expense": float(totals["highest_expense"]),
        "by_category": [
            {
                "expense_category": row.expense_category,
                "label": ExpenseCategory(row.expense_category).label,
                "total": float(row.total),
                "count": row.count,
            }
            for row in rows
        ],
    }


@router.get(
    "/{expense_id}",
    response_model=ExpenseRead,
    summary="Get one expense",
    description="Runs the `select_expense_by_id` statement from sql/queries/expenses.sql.",
)
async def get_expense(db: DbSession, expense_id: int = Path(gt=0)) -> ExpenseRead:
    row = (await db.execute(_SELECT_EXPENSE_BY_ID, {"id": expense_id})).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Expense {expense_id} does not exist")
    return _row_to_read(row)


# ----------------------------------------------------- update / delete ----
@router.put("/{expense_id}", response_model=ExpenseRead, summary="Update an expense (partial)")
async def update_expense(
    payload: ExpenseUpdate, db: DbSession, expense_id: int = Path(gt=0)
) -> ExpenseRead:
    expense = await _get_orm_or_404(db, expense_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    await db.commit()
    await db.refresh(expense)
    return ExpenseRead.model_validate(expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_expense(db: DbSession, expense_id: int = Path(gt=0)) -> Response:
    expense = await _get_orm_or_404(db, expense_id)
    await db.delete(expense)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
