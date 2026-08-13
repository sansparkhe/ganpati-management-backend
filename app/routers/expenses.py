"""Expense endpoints — /api/expenses"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Path, Query, status

from app.dependencies import Actor, DbSession, ExpenseFilterParams, Pagination
from app.models.enums import AuditEntity
from app.schemas.audit import AuditHistoryResponse, AuditLogRead
from app.schemas.common import APIResponse, DeletedResponse, Page
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseSummary, ExpenseUpdate
from app.services import audit_service, expense_service
from app.utils.responses import ERROR_RESPONSES, envelope, paginated

router = APIRouter(prefix="/expenses", tags=["Expenses"], responses=ERROR_RESPONSES)


@router.get(
    "",
    response_model=APIResponse[Page[ExpenseRead]],
    summary="List expenses (paginated + filterable + searchable)",
    description=(
        "Filters: `category` (code), `category_id`, `payment_method`, "
        "`date_from`, `date_to`, `min_amount`, `max_amount`, `search`. "
        "Pagination: `page` (1-based) and `limit`."
    ),
)
async def list_expenses(
    db: DbSession, filters: ExpenseFilterParams, pagination: Pagination
) -> dict:
    rows, total = await expense_service.list_expenses(db, filters, pagination)
    return paginated(
        [ExpenseRead.model_validate(row) for row in rows],
        total,
        pagination,
        "Expenses fetched successfully",
    )


@router.get(
    "/summary",
    response_model=APIResponse[ExpenseSummary],
    summary="Expense summary (totals by category and payment method)",
)
async def expense_summary(
    db: DbSession,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> dict:
    summary = await expense_service.build_summary(db, date_from=date_from, date_to=date_to)
    return envelope(ExpenseSummary(**summary), "Expense summary generated successfully")


@router.get(
    "/{expense_id}",
    response_model=APIResponse[ExpenseRead],
    summary="Get one expense",
)
async def get_expense(db: DbSession, expense_id: int = Path(gt=0)) -> dict:
    expense = await expense_service.get_expense(db, expense_id)
    return envelope(ExpenseRead.model_validate(expense), "Expense fetched successfully")


@router.get(
    "/{expense_id}/history",
    response_model=APIResponse[AuditHistoryResponse],
    summary="Audit trail for one expense",
    description="Shows exactly what changed, e.g. amount 3000.00 -> 3500.00, and when.",
)
async def expense_history(db: DbSession, expense_id: int = Path(gt=0)) -> dict:
    await expense_service.get_expense(db, expense_id)
    logs = await audit_service.history_for(
        db, entity_type=AuditEntity.EXPENSE, entity_id=expense_id
    )
    payload = AuditHistoryResponse(
        entity_type=AuditEntity.EXPENSE,
        entity_id=expense_id,
        items=[AuditLogRead.model_validate(log) for log in logs],
        total=len(logs),
    )
    return envelope(payload, "Expense history fetched successfully")


@router.post(
    "",
    response_model=APIResponse[ExpenseRead],
    status_code=status.HTTP_201_CREATED,
    summary="Record an expense",
    description='Send either `category_id` or `category_code` (e.g. "DECORATION").',
)
async def create_expense(db: DbSession, payload: ExpenseCreate, actor: Actor) -> dict:
    expense = await expense_service.create_expense(db, payload, actor=actor)
    return envelope(ExpenseRead.model_validate(expense), "Expense created successfully")


@router.put(
    "/{expense_id}",
    response_model=APIResponse[ExpenseRead],
    summary="Update an expense (partial - send only what changes)",
    description="Every change is written to the audit log; pass `audit_note` to record why.",
)
async def update_expense(
    db: DbSession, payload: ExpenseUpdate, actor: Actor, expense_id: int = Path(gt=0)
) -> dict:
    expense = await expense_service.update_expense(db, expense_id, payload, actor=actor)
    return envelope(ExpenseRead.model_validate(expense), "Expense updated successfully")


@router.patch(
    "/{expense_id}",
    response_model=APIResponse[ExpenseRead],
    summary="Alias of PUT for clients that prefer PATCH",
)
async def patch_expense(
    db: DbSession, payload: ExpenseUpdate, actor: Actor, expense_id: int = Path(gt=0)
) -> dict:
    return await update_expense(db=db, payload=payload, actor=actor, expense_id=expense_id)


@router.delete(
    "/{expense_id}",
    response_model=APIResponse[DeletedResponse],
    summary="Delete an expense",
    description="The deleted row is preserved in the audit log as a snapshot.",
)
async def delete_expense(
    db: DbSession,
    actor: Actor,
    expense_id: int = Path(gt=0),
    reason: str | None = Query(None, max_length=500, description="Stored in the audit log"),
) -> dict:
    await expense_service.delete_expense(db, expense_id, actor=actor, note=reason)
    return envelope(DeletedResponse(id=expense_id), "Expense deleted successfully")
