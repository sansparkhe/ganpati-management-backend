"""Expense category business logic."""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CategoryInUseError,
    CategoryNotFoundError,
    DuplicateCategoryError,
)
from app.models.category import ExpenseCategory
from app.models.enums import AuditAction, AuditEntity
from app.models.expense import Expense
from app.schemas.category import ExpenseCategoryCreate, ExpenseCategoryUpdate
from app.services import audit_service

# Seeded on first run; fully editable afterwards through the API.
DEFAULT_CATEGORIES: list[tuple[str, str, str]] = [
    ("DECORATION", "Decoration", "Mandap, lights, flowers, backdrop"),
    ("FOOD", "Food", "Meals and refreshments for volunteers and guests"),
    ("SOUND", "Sound", "Speakers, DJ, microphones"),
    ("ELECTRICITY", "Electricity", "Wiring, meter charges, generator fuel"),
    ("POOJA", "Pooja", "Pooja saman, guruji dakshina, idol"),
    ("PRASAD", "Prasad", "Modak, prasad distribution"),
    ("CLEANING", "Cleaning", "Housekeeping and waste disposal"),
    ("TRANSPORTATION", "Transportation", "Idol transport, tempo, visarjan vehicle"),
    ("ADVERTISEMENT", "Advertisement", "Banners, hoardings, printing"),
    ("MISCELLANEOUS", "Miscellaneous", "Anything that does not fit elsewhere"),
]


def _derive_code(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_").upper()


async def list_categories(
    db: AsyncSession, *, is_active: bool | None = None, search: str | None = None
) -> Sequence[ExpenseCategory]:
    stmt = select(ExpenseCategory)
    if is_active is not None:
        stmt = stmt.where(ExpenseCategory.is_active.is_(is_active))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(ExpenseCategory.name.ilike(pattern) | ExpenseCategory.code.ilike(pattern))
    stmt = stmt.order_by(ExpenseCategory.sort_order, ExpenseCategory.name)
    return (await db.execute(stmt)).scalars().all()


async def get_category(db: AsyncSession, category_id: int) -> ExpenseCategory:
    category = await db.get(ExpenseCategory, category_id)
    if category is None:
        raise CategoryNotFoundError(category_id=category_id)
    return category


async def get_category_by_code(db: AsyncSession, code: str) -> ExpenseCategory:
    stmt = select(ExpenseCategory).where(ExpenseCategory.code == code.strip().upper())
    category = (await db.execute(stmt)).scalars().first()
    if category is None:
        raise CategoryNotFoundError(code=code.strip().upper())
    return category


async def resolve_category(
    db: AsyncSession, *, category_id: int | None, category_code: str | None
) -> ExpenseCategory:
    """Accept either the id or the code — whichever the client finds easier."""
    if category_id is not None:
        return await get_category(db, category_id)
    if category_code:
        return await get_category_by_code(db, category_code)
    raise CategoryNotFoundError(code="<missing>")


async def create_category(
    db: AsyncSession, payload: ExpenseCategoryCreate, *, actor: str | None = None
) -> ExpenseCategory:
    code = payload.code or _derive_code(payload.name)
    existing = (
        (await db.execute(select(ExpenseCategory).where(ExpenseCategory.code == code)))
        .scalars()
        .first()
    )
    if existing is not None:
        raise DuplicateCategoryError(code)

    category = ExpenseCategory(
        code=code,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        is_system=False,
    )
    db.add(category)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.EXPENSE_CATEGORY,
        entity_id=category.id,
        action=AuditAction.CREATE,
        after=audit_service.snapshot_of(category),
        actor=actor,
    )
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession,
    category_id: int,
    payload: ExpenseCategoryUpdate,
    *,
    actor: str | None = None,
) -> ExpenseCategory:
    category = await get_category(db, category_id)
    before = audit_service.snapshot_of(category)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.EXPENSE_CATEGORY,
        entity_id=category.id,
        action=AuditAction.UPDATE,
        before=before,
        after=audit_service.snapshot_of(category),
        actor=actor,
    )
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category_id: int, *, actor: str | None = None) -> None:
    category = await get_category(db, category_id)
    count_stmt = select(func.count()).select_from(Expense).where(Expense.category_id == category_id)
    expense_count = int((await db.execute(count_stmt)).scalar_one())
    if expense_count:
        raise CategoryInUseError(category.code, expense_count)

    snapshot = audit_service.snapshot_of(category)
    await db.delete(category)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.EXPENSE_CATEGORY,
        entity_id=category_id,
        action=AuditAction.DELETE,
        before=snapshot,
        actor=actor,
    )
    await db.commit()


async def ensure_default_categories(db: AsyncSession) -> list[ExpenseCategory]:
    """Idempotently insert the default categories (used by the seed script)."""
    created: list[ExpenseCategory] = []
    existing_codes = {code for (code,) in (await db.execute(select(ExpenseCategory.code))).all()}
    for index, (code, name, description) in enumerate(DEFAULT_CATEGORIES):
        if code in existing_codes:
            continue
        category = ExpenseCategory(
            code=code,
            name=name,
            description=description,
            is_active=True,
            sort_order=(index + 1) * 10,
            is_system=True,
        )
        db.add(category)
        created.append(category)
    if created:
        await db.commit()
        for category in created:
            await db.refresh(category)
    return created
