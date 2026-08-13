"""Expense business logic: CRUD, filtering, search and aggregations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import BadRequestError, ExpenseNotFoundError
from app.models.category import ExpenseCategory
from app.models.enums import AuditAction, AuditEntity, PaymentMethod
from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services import audit_service, category_service
from app.utils.money import ZERO, percentage, to_money
from app.utils.pagination import PaginationParams


@dataclass(frozen=True)
class ExpenseFilters:
    category_id: int | None = None
    category_code: str | None = None
    payment_method: PaymentMethod | None = None
    date_from: date | None = None
    date_to: date | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    search: str | None = None


def _apply_filters(stmt: Select, filters: ExpenseFilters) -> Select:
    if filters.category_id is not None:
        stmt = stmt.where(Expense.category_id == filters.category_id)
    if filters.category_code:
        stmt = stmt.where(ExpenseCategory.code == filters.category_code.strip().upper())
    if filters.payment_method is not None:
        stmt = stmt.where(Expense.payment_method == filters.payment_method)
    if filters.date_from is not None:
        stmt = stmt.where(Expense.spent_on >= filters.date_from)
    if filters.date_to is not None:
        stmt = stmt.where(Expense.spent_on <= filters.date_to)
    if filters.min_amount is not None:
        stmt = stmt.where(Expense.amount >= filters.min_amount)
    if filters.max_amount is not None:
        stmt = stmt.where(Expense.amount <= filters.max_amount)
    if filters.search:
        pattern = f"%{filters.search.strip()}%"
        stmt = stmt.where(
            or_(
                Expense.title.ilike(pattern),
                Expense.description.ilike(pattern),
                Expense.vendor.ilike(pattern),
                Expense.reference_no.ilike(pattern),
                Expense.notes.ilike(pattern),
                Expense.paid_by.ilike(pattern),
            )
        )
    return stmt


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise BadRequestError("date_from cannot be after date_to", error_code="INVALID_DATE_RANGE")


# ---------------------------------------------------------------- CRUD ----
async def get_expense(db: AsyncSession, expense_id: int) -> Expense:
    """Always re-reads with the category eagerly joined (see get_collection)."""
    stmt = (
        select(Expense)
        .options(joinedload(Expense.category))
        .where(Expense.id == expense_id)
        .execution_options(populate_existing=True)
    )
    expense = (await db.execute(stmt)).scalars().unique().first()
    if expense is None:
        raise ExpenseNotFoundError(expense_id)
    return expense


async def list_expenses(
    db: AsyncSession, filters: ExpenseFilters, pagination: PaginationParams
) -> tuple[Sequence[Expense], int]:
    _validate_date_range(filters.date_from, filters.date_to)

    base = select(Expense).join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
    base = _apply_filters(base, filters)

    count_stmt = _apply_filters(
        select(func.count(Expense.id))
        .select_from(Expense)
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id),
        filters,
    )
    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(Expense.spent_on.desc(), Expense.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    rows = (await db.execute(stmt)).scalars().unique().all()
    return rows, total


async def create_expense(
    db: AsyncSession, payload: ExpenseCreate, *, actor: str | None = None
) -> Expense:
    category = await category_service.resolve_category(
        db, category_id=payload.category_id, category_code=payload.category_code
    )
    expense = Expense(
        category_id=category.id,
        title=payload.title,
        description=payload.description,
        amount=payload.amount,
        payment_method=payload.payment_method,
        spent_on=payload.spent_on or date.today(),
        vendor=payload.vendor,
        reference_no=payload.reference_no,
        paid_by=payload.paid_by,
        notes=payload.notes,
    )
    db.add(expense)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.EXPENSE,
        entity_id=expense.id,
        action=AuditAction.CREATE,
        after=audit_service.snapshot_of(expense),
        actor=actor,
    )
    await db.commit()
    return await get_expense(db, expense.id)


async def update_expense(
    db: AsyncSession, expense_id: int, payload: ExpenseUpdate, *, actor: str | None = None
) -> Expense:
    expense = await get_expense(db, expense_id)
    before = audit_service.snapshot_of(expense)

    data = payload.model_dump(exclude_unset=True)
    note = data.pop("audit_note", None)
    category_id = data.pop("category_id", None)
    category_code = data.pop("category_code", None)

    if category_id is not None or category_code:
        category = await category_service.resolve_category(
            db, category_id=category_id, category_code=category_code
        )
        expense.category_id = category.id

    for field, value in data.items():
        setattr(expense, field, value)

    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.EXPENSE,
        entity_id=expense.id,
        action=AuditAction.UPDATE,
        before=before,
        after=audit_service.snapshot_of(expense),
        actor=actor,
        note=note,
    )
    await db.commit()
    return await get_expense(db, expense.id)


async def delete_expense(
    db: AsyncSession, expense_id: int, *, actor: str | None = None, note: str | None = None
) -> None:
    expense = await get_expense(db, expense_id)
    snapshot = audit_service.snapshot_of(expense)
    await db.delete(expense)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.EXPENSE,
        entity_id=expense_id,
        action=AuditAction.DELETE,
        before=snapshot,
        actor=actor,
        note=note,
    )
    await db.commit()


# --------------------------------------------------------- aggregations ----
def _range_conditions(date_from: date | None, date_to: date | None) -> list:
    conditions = []
    if date_from:
        conditions.append(Expense.spent_on >= date_from)
    if date_to:
        conditions.append(Expense.spent_on <= date_to)
    return conditions


async def total_spent(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> tuple[Decimal, int]:
    stmt = select(func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id)).where(
        *_range_conditions(date_from, date_to)
    )
    total, count = (await db.execute(stmt)).one()
    return to_money(total), int(count)


async def totals_by_payment_method(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> list[dict[str, Any]]:
    stmt = (
        select(
            Expense.payment_method,
            func.coalesce(func.sum(Expense.amount), 0),
            func.count(Expense.id),
        )
        .where(*_range_conditions(date_from, date_to))
        .group_by(Expense.payment_method)
    )
    rows = {method: (total, count) for method, total, count in (await db.execute(stmt)).all()}
    return [
        {
            "payment_method": method,
            "label": method.label,
            "total": to_money(rows.get(method, (ZERO, 0))[0]),
            "count": int(rows.get(method, (ZERO, 0))[1]),
        }
        for method in PaymentMethod
    ]


async def totals_by_category(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    include_empty: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    # Date filters belong in the JOIN condition, not the WHERE clause, so that
    # categories with no matching expense still appear (with a zero total).
    join_condition = and_(
        Expense.category_id == ExpenseCategory.id,
        *_range_conditions(date_from, date_to),
    )
    stmt = (
        select(
            ExpenseCategory.id,
            ExpenseCategory.code,
            ExpenseCategory.name,
            func.coalesce(func.sum(Expense.amount), 0),
            func.count(Expense.id),
        )
        .select_from(ExpenseCategory)
        .outerjoin(Expense, join_condition)
        .group_by(ExpenseCategory.id, ExpenseCategory.code, ExpenseCategory.name)
    )
    rows = (await db.execute(stmt)).all()
    grand_total = to_money(sum((to_money(row[3]) for row in rows), start=ZERO))

    results = [
        {
            "category_id": category_id,
            "category_code": code,
            "category_name": name,
            "total": to_money(total),
            "count": int(count),
            "percentage": percentage(to_money(total), grand_total),
        }
        for category_id, code, name, total, count in rows
    ]
    if not include_empty:
        results = [row for row in results if row["count"] > 0]
    results.sort(key=lambda row: (-row["total"], row["category_name"]))
    if limit is not None:
        results = results[:limit]
    return results


async def recent_expenses(db: AsyncSession, limit: int) -> Sequence[Expense]:
    stmt = select(Expense).order_by(Expense.created_at.desc(), Expense.id.desc()).limit(limit)
    return (await db.execute(stmt)).scalars().unique().all()


async def build_summary(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> dict[str, Any]:
    _validate_date_range(date_from, date_to)

    total, count = await total_spent(db, date_from=date_from, date_to=date_to)
    highest_stmt = select(func.coalesce(func.max(Expense.amount), 0)).where(
        *_range_conditions(date_from, date_to)
    )
    highest = to_money((await db.execute(highest_stmt)).scalar_one())
    by_method = await totals_by_payment_method(db, date_from=date_from, date_to=date_to)
    method_totals = {row["payment_method"]: row["total"] for row in by_method}

    return {
        "total_expenses": total,
        "expense_count": count,
        "average_expense": to_money(total / count) if count else ZERO,
        "highest_expense": highest,
        "total_cash": method_totals[PaymentMethod.CASH],
        "total_upi": method_totals[PaymentMethod.UPI],
        "total_bank_transfer": method_totals[PaymentMethod.BANK_TRANSFER],
        "total_other": method_totals[PaymentMethod.OTHER],
        "by_category": await totals_by_category(db, date_from=date_from, date_to=date_to),
        "by_payment_method": by_method,
    }
