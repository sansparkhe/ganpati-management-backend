"""Collection business logic: CRUD, filtering and every money aggregation.

Nothing here ever trusts a client supplied total. Every number is computed
from the `collections` rows by the database.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import BadRequestError, CollectionNotFoundError
from app.models.collection import Collection
from app.models.enums import AuditAction, AuditEntity, CollectionStatus, PaymentMethod
from app.models.flat import Flat
from app.schemas.collection import CollectionCreate, CollectionUpdate
from app.services import audit_service, flat_service
from app.utils.money import ZERO, percentage, to_money
from app.utils.pagination import PaginationParams


@dataclass(frozen=True)
class CollectionFilters:
    flat_id: int | None = None
    wing: str | None = None
    payment_method: PaymentMethod | None = None
    status: CollectionStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    search: str | None = None


def _apply_filters(stmt: Select, filters: CollectionFilters) -> Select:
    if filters.flat_id is not None:
        stmt = stmt.where(Collection.flat_id == filters.flat_id)
    if filters.wing:
        stmt = stmt.where(Flat.wing == flat_service.validate_wing(filters.wing))
    if filters.payment_method is not None:
        stmt = stmt.where(Collection.payment_method == filters.payment_method)
    if filters.status is not None:
        stmt = stmt.where(Collection.status == filters.status)
    if filters.date_from is not None:
        stmt = stmt.where(Collection.collected_on >= filters.date_from)
    if filters.date_to is not None:
        stmt = stmt.where(Collection.collected_on <= filters.date_to)
    if filters.min_amount is not None:
        stmt = stmt.where(Collection.amount >= filters.min_amount)
    if filters.max_amount is not None:
        stmt = stmt.where(Collection.amount <= filters.max_amount)
    if filters.search:
        pattern = f"%{filters.search.strip()}%"
        stmt = stmt.where(
            or_(
                Collection.notes.ilike(pattern),
                Collection.reference_no.ilike(pattern),
                Collection.collected_by.ilike(pattern),
                Flat.flat_number.ilike(pattern),
                Flat.owner_name.ilike(pattern),
            )
        )
    return stmt


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise BadRequestError("date_from cannot be after date_to", error_code="INVALID_DATE_RANGE")


# ---------------------------------------------------------------- CRUD ----
async def get_collection(db: AsyncSession, collection_id: int) -> Collection:
    """Always re-reads with the flat eagerly joined.

    `session.get()` would return a cached instance whose `flat` relationship is
    not loaded, which then explodes at serialisation time in an async session.
    """
    stmt = (
        select(Collection)
        .options(joinedload(Collection.flat))
        .where(Collection.id == collection_id)
        .execution_options(populate_existing=True)
    )
    collection = (await db.execute(stmt)).scalars().unique().first()
    if collection is None:
        raise CollectionNotFoundError(collection_id)
    return collection


async def list_collections(
    db: AsyncSession, filters: CollectionFilters, pagination: PaginationParams
) -> tuple[Sequence[Collection], int]:
    _validate_date_range(filters.date_from, filters.date_to)

    base = select(Collection).join(Flat, Collection.flat_id == Flat.id)
    base = _apply_filters(base, filters)

    count_stmt = _apply_filters(
        select(func.count(Collection.id))
        .select_from(Collection)
        .join(Flat, Collection.flat_id == Flat.id),
        filters,
    )
    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(Collection.collected_on.desc(), Collection.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    rows = (await db.execute(stmt)).scalars().unique().all()
    return rows, total


async def create_collection(
    db: AsyncSession, payload: CollectionCreate, *, actor: str | None = None
) -> Collection:
    # Raises FLAT_NOT_FOUND — a collection can never reference a missing flat.
    flat = await flat_service.get_flat(db, payload.flat_id)

    collection = Collection(
        flat_id=flat.id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        status=payload.status,
        collected_on=payload.collected_on or date.today(),
        reference_no=payload.reference_no,
        collected_by=payload.collected_by,
        notes=payload.notes,
    )
    db.add(collection)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.COLLECTION,
        entity_id=collection.id,
        action=AuditAction.CREATE,
        after=audit_service.snapshot_of(collection),
        actor=actor,
    )
    await db.commit()
    return await get_collection(db, collection.id)


async def update_collection(
    db: AsyncSession, collection_id: int, payload: CollectionUpdate, *, actor: str | None = None
) -> Collection:
    collection = await get_collection(db, collection_id)
    before = audit_service.snapshot_of(collection)

    data = payload.model_dump(exclude_unset=True)
    note = data.pop("audit_note", None)

    if "flat_id" in data and data["flat_id"] is not None:
        await flat_service.get_flat(db, data["flat_id"])

    for field, value in data.items():
        setattr(collection, field, value)

    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.COLLECTION,
        entity_id=collection.id,
        action=AuditAction.UPDATE,
        before=before,
        after=audit_service.snapshot_of(collection),
        actor=actor,
        note=note,
    )
    await db.commit()
    return await get_collection(db, collection.id)


async def delete_collection(
    db: AsyncSession, collection_id: int, *, actor: str | None = None, note: str | None = None
) -> None:
    collection = await get_collection(db, collection_id)
    snapshot = audit_service.snapshot_of(collection)
    await db.delete(collection)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.COLLECTION,
        entity_id=collection_id,
        action=AuditAction.DELETE,
        before=snapshot,
        actor=actor,
        note=note,
    )
    await db.commit()


# --------------------------------------------------------- aggregations ----
def _confirmed(*extra) -> list:
    return [Collection.status == CollectionStatus.CONFIRMED, *extra]


def _range_conditions(date_from: date | None, date_to: date | None) -> list:
    conditions = []
    if date_from:
        conditions.append(Collection.collected_on >= date_from)
    if date_to:
        conditions.append(Collection.collected_on <= date_to)
    return conditions


async def total_collected(
    db: AsyncSession,
    *,
    status: CollectionStatus = CollectionStatus.CONFIRMED,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[Decimal, int]:
    """(total amount, transaction count) for a status."""
    stmt = select(func.coalesce(func.sum(Collection.amount), 0), func.count(Collection.id)).where(
        Collection.status == status, *_range_conditions(date_from, date_to)
    )
    total, count = (await db.execute(stmt)).one()
    return to_money(total), int(count)


async def totals_by_payment_method(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> list[dict[str, Any]]:
    stmt = (
        select(
            Collection.payment_method,
            func.coalesce(func.sum(Collection.amount), 0),
            func.count(Collection.id),
        )
        .where(*_confirmed(*_range_conditions(date_from, date_to)))
        .group_by(Collection.payment_method)
    )
    rows = {method: (total, count) for method, total, count in (await db.execute(stmt)).all()}
    # Always return every method so the Flutter chart has stable series.
    return [
        {
            "payment_method": method,
            "label": method.label,
            "total": to_money(rows.get(method, (ZERO, 0))[0]),
            "count": int(rows.get(method, (ZERO, 0))[1]),
        }
        for method in PaymentMethod
    ]


async def totals_by_status(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(
        Collection.status,
        func.coalesce(func.sum(Collection.amount), 0),
        func.count(Collection.id),
    ).group_by(Collection.status)
    rows = {status: (total, count) for status, total, count in (await db.execute(stmt)).all()}
    return [
        {
            "status": status,
            "total": to_money(rows.get(status, (ZERO, 0))[0]),
            "count": int(rows.get(status, (ZERO, 0))[1]),
        }
        for status in CollectionStatus
    ]


async def contributions_by_flat(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> list[dict[str, Any]]:
    """Every flat with its total — including flats that contributed nothing."""
    join_condition = and_(
        Collection.flat_id == Flat.id,
        Collection.status == CollectionStatus.CONFIRMED,
        *_range_conditions(date_from, date_to),
    )
    stmt = (
        select(
            Flat.id,
            Flat.wing,
            Flat.flat_number,
            Flat.display_name,
            Flat.owner_name,
            Flat.is_active,
            func.coalesce(func.sum(Collection.amount), 0),
            func.count(Collection.id),
            func.max(Collection.collected_on),
        )
        .select_from(Flat)
        .outerjoin(Collection, join_condition)
        .group_by(
            Flat.id, Flat.wing, Flat.flat_number, Flat.display_name, Flat.owner_name, Flat.is_active
        )
        .order_by(Flat.sort_order, Flat.flat_number)
    )
    results: list[dict[str, Any]] = []
    for (
        flat_id,
        wing,
        flat_number,
        display_name,
        owner_name,
        is_active,
        total,
        count,
        last_on,
    ) in (await db.execute(stmt)).all():
        count = int(count)
        # Inactive flats only appear if they actually contributed something.
        if not is_active and count == 0:
            continue
        results.append(
            {
                "flat_id": flat_id,
                "wing": wing,
                "flat_number": flat_number,
                "display_name": display_name,
                "owner_name": owner_name,
                "total_amount": to_money(total),
                "collection_count": count,
                "has_contributed": count > 0,
                "last_collected_on": _as_date(last_on),
                "is_active": bool(is_active),
            }
        )
    return results


def _as_date(value: Any) -> date | None:
    """SQLite returns dates as strings; PostgreSQL returns `date` objects."""
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


async def totals_by_wing(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> list[dict[str, Any]]:
    per_flat = await contributions_by_flat(db, date_from=date_from, date_to=date_to)
    active_flat_counts = await _active_flat_count_by_wing(db)

    buckets: dict[str, dict[str, Any]] = {}
    for wing in sorted({*active_flat_counts, *(row["wing"] for row in per_flat)}):
        buckets[wing] = {
            "wing": wing,
            "total": ZERO,
            "count": 0,
            "flats_total": active_flat_counts.get(wing, 0),
            "flats_contributed": 0,
            "flats_pending": 0,
        }
    for row in per_flat:
        bucket = buckets[row["wing"]]
        bucket["total"] = to_money(bucket["total"] + row["total_amount"])
        bucket["count"] += row["collection_count"]
        if row["has_contributed"]:
            bucket["flats_contributed"] += 1
    for bucket in buckets.values():
        bucket["flats_pending"] = max(bucket["flats_total"] - bucket["flats_contributed"], 0)
    return list(buckets.values())


async def _active_flat_count_by_wing(db: AsyncSession) -> dict[str, int]:
    stmt = (
        select(Flat.wing, func.count(Flat.id)).where(Flat.is_active.is_(True)).group_by(Flat.wing)
    )
    return {wing: int(count) for wing, count in (await db.execute(stmt)).all()}


async def pending_flats(db: AsyncSession) -> list[Flat]:
    """Active flats with no CONFIRMED collection yet."""
    contributed = (
        select(Collection.flat_id).where(Collection.status == CollectionStatus.CONFIRMED).distinct()
    )
    stmt = (
        select(Flat)
        .where(Flat.is_active.is_(True), Flat.id.not_in(contributed))
        .order_by(Flat.sort_order, Flat.flat_number)
    )
    return list((await db.execute(stmt)).scalars().all())


async def flat_participation(db: AsyncSession) -> tuple[int, int, int]:
    """(active flats, flats that contributed, flats that have not)."""
    active_stmt = select(func.count(Flat.id)).where(Flat.is_active.is_(True))
    active = int((await db.execute(active_stmt)).scalar_one())

    contributed_stmt = (
        select(func.count(func.distinct(Collection.flat_id)))
        .select_from(Collection)
        .join(Flat, Collection.flat_id == Flat.id)
        .where(Collection.status == CollectionStatus.CONFIRMED, Flat.is_active.is_(True))
    )
    contributed = int((await db.execute(contributed_stmt)).scalar_one())
    return active, contributed, max(active - contributed, 0)


async def recent_collections(db: AsyncSession, limit: int) -> Sequence[Collection]:
    stmt = (
        select(Collection).order_by(Collection.created_at.desc(), Collection.id.desc()).limit(limit)
    )
    return (await db.execute(stmt)).scalars().unique().all()


async def collections_for_flat(
    db: AsyncSession, flat_id: int
) -> tuple[Flat, list[Collection], Decimal]:
    flat = await flat_service.get_flat(db, flat_id)
    stmt = (
        select(Collection)
        .where(Collection.flat_id == flat_id)
        .order_by(Collection.collected_on.desc(), Collection.id.desc())
    )
    rows = list((await db.execute(stmt)).scalars().unique().all())
    total = to_money(
        sum(
            (row.amount for row in rows if row.status == CollectionStatus.CONFIRMED),
            start=ZERO,
        )
    )
    return flat, rows, total


async def build_summary(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> dict[str, Any]:
    """Everything requirement #2 asks the summary endpoint to return."""
    _validate_date_range(date_from, date_to)

    confirmed_total, confirmed_count = await total_collected(
        db, status=CollectionStatus.CONFIRMED, date_from=date_from, date_to=date_to
    )
    pending_total, _ = await total_collected(
        db, status=CollectionStatus.PENDING, date_from=date_from, date_to=date_to
    )
    cancelled_total, _ = await total_collected(
        db, status=CollectionStatus.CANCELLED, date_from=date_from, date_to=date_to
    )

    by_method = await totals_by_payment_method(db, date_from=date_from, date_to=date_to)
    by_status = await totals_by_status(db)
    by_flat = await contributions_by_flat(db, date_from=date_from, date_to=date_to)
    by_wing = await totals_by_wing(db, date_from=date_from, date_to=date_to)
    active_flats, contributed, not_contributed = await flat_participation(db)

    method_totals = {row["payment_method"]: row["total"] for row in by_method}
    contributing = [row for row in by_flat if row["has_contributed"]]
    highest = max((row["total_amount"] for row in contributing), default=ZERO)
    average = to_money(confirmed_total / len(contributing)) if contributing else ZERO

    return {
        "total_collection": confirmed_total,
        "pending_amount": pending_total,
        "cancelled_amount": cancelled_total,
        "collection_count": confirmed_count,
        "total_flats": active_flats,
        "flats_contributed": contributed,
        "flats_not_contributed": not_contributed,
        "contribution_percentage": percentage(contributed, active_flats),
        "average_per_contributing_flat": average,
        "highest_contribution": to_money(highest),
        "total_cash": method_totals[PaymentMethod.CASH],
        "total_upi": method_totals[PaymentMethod.UPI],
        "total_bank_transfer": method_totals[PaymentMethod.BANK_TRANSFER],
        "total_other": method_totals[PaymentMethod.OTHER],
        "by_payment_method": by_method,
        "by_status": by_status,
        "by_wing": by_wing,
        "by_flat": by_flat,
    }
