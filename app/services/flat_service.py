"""Flat business logic."""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    DuplicateFlatError,
    FlatHasCollectionsError,
    FlatNotFoundError,
    InvalidWingError,
)
from app.models.collection import Collection
from app.models.enums import AuditAction, AuditEntity
from app.models.flat import Flat
from app.schemas.flat import FlatCreate, FlatUpdate
from app.services import audit_service

_TRAILING_NUMBER = re.compile(r"(\d+)\s*$")


def validate_wing(wing: str) -> str:
    """Wings are configuration, not a hard-coded enum."""
    normalised = wing.strip().upper()
    if normalised not in settings.wing_codes:
        raise InvalidWingError(normalised, settings.wing_codes)
    return normalised


def derive_sort_order(wing: str, flat_number: str) -> int:
    """Wing-major ordering so A2 comes before A10 (string sort would not)."""
    match = _TRAILING_NUMBER.search(flat_number)
    number = int(match.group(1)) if match else 0
    codes = settings.wing_codes
    wing_index = codes.index(wing) if wing in codes else len(codes)
    return wing_index * 1000 + number


async def get_flat(db: AsyncSession, flat_id: int) -> Flat:
    flat = await db.get(Flat, flat_id)
    if flat is None:
        raise FlatNotFoundError(flat_id=flat_id)
    return flat


async def get_flat_by_number(db: AsyncSession, flat_number: str) -> Flat | None:
    stmt = select(Flat).where(Flat.flat_number == flat_number.strip().upper())
    return (await db.execute(stmt)).scalars().first()


async def list_flats(
    db: AsyncSession,
    *,
    wing: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> Sequence[Flat]:
    stmt = select(Flat)
    if wing:
        stmt = stmt.where(Flat.wing == validate_wing(wing))
    if is_active is not None:
        stmt = stmt.where(Flat.is_active.is_(is_active))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Flat.flat_number.ilike(pattern),
                Flat.display_name.ilike(pattern),
                Flat.owner_name.ilike(pattern),
                Flat.phone.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Flat.sort_order, Flat.flat_number)
    return (await db.execute(stmt)).scalars().unique().all()


async def count_flats(db: AsyncSession, *, is_active: bool | None = None) -> int:
    stmt = select(func.count(Flat.id))
    if is_active is not None:
        stmt = stmt.where(Flat.is_active.is_(is_active))
    return int((await db.execute(stmt)).scalar_one())


async def create_flat(db: AsyncSession, payload: FlatCreate, *, actor: str | None = None) -> Flat:
    wing = validate_wing(payload.wing)
    flat_number = payload.flat_number

    if await get_flat_by_number(db, flat_number) is not None:
        raise DuplicateFlatError(flat_number)

    flat = Flat(
        wing=wing,
        flat_number=flat_number,
        display_name=payload.display_name or flat_number,
        owner_name=payload.owner_name,
        phone=payload.phone,
        notes=payload.notes,
        is_active=payload.is_active,
        sort_order=payload.sort_order
        if payload.sort_order is not None
        else derive_sort_order(wing, flat_number),
    )
    db.add(flat)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.FLAT,
        entity_id=flat.id,
        action=AuditAction.CREATE,
        after=audit_service.snapshot_of(flat),
        actor=actor,
    )
    await db.commit()
    await db.refresh(flat)
    return flat


async def bulk_create_flats(
    db: AsyncSession,
    payloads: list[FlatCreate],
    *,
    skip_existing: bool = True,
    actor: str | None = None,
) -> tuple[list[Flat], list[str]]:
    created: list[Flat] = []
    skipped: list[str] = []
    seen: set[str] = set()

    for payload in payloads:
        wing = validate_wing(payload.wing)
        flat_number = payload.flat_number
        exists = flat_number in seen or await get_flat_by_number(db, flat_number) is not None
        if exists:
            if skip_existing:
                skipped.append(flat_number)
                continue
            raise DuplicateFlatError(flat_number)

        flat = Flat(
            wing=wing,
            flat_number=flat_number,
            display_name=payload.display_name or flat_number,
            owner_name=payload.owner_name,
            phone=payload.phone,
            notes=payload.notes,
            is_active=payload.is_active,
            sort_order=payload.sort_order
            if payload.sort_order is not None
            else derive_sort_order(wing, flat_number),
        )
        db.add(flat)
        seen.add(flat_number)
        created.append(flat)

    await db.flush()
    for flat in created:
        await audit_service.record(
            db,
            entity_type=AuditEntity.FLAT,
            entity_id=flat.id,
            action=AuditAction.CREATE,
            after=audit_service.snapshot_of(flat),
            actor=actor,
            note="bulk create",
        )
    await db.commit()
    for flat in created:
        await db.refresh(flat)
    return created, skipped


async def update_flat(
    db: AsyncSession, flat_id: int, payload: FlatUpdate, *, actor: str | None = None
) -> Flat:
    flat = await get_flat(db, flat_id)
    before = audit_service.snapshot_of(flat)
    data = payload.model_dump(exclude_unset=True)

    if "wing" in data and data["wing"] is not None:
        data["wing"] = validate_wing(data["wing"])
    if "flat_number" in data and data["flat_number"] is not None:
        existing = await get_flat_by_number(db, data["flat_number"])
        if existing is not None and existing.id != flat.id:
            raise DuplicateFlatError(data["flat_number"])

    for field, value in data.items():
        setattr(flat, field, value)

    if ("wing" in data or "flat_number" in data) and "sort_order" not in data:
        flat.sort_order = derive_sort_order(flat.wing, flat.flat_number)

    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.FLAT,
        entity_id=flat.id,
        action=AuditAction.UPDATE,
        before=before,
        after=audit_service.snapshot_of(flat),
        actor=actor,
    )
    await db.commit()
    await db.refresh(flat)
    return flat


async def delete_flat(db: AsyncSession, flat_id: int, *, actor: str | None = None) -> None:
    flat = await get_flat(db, flat_id)
    count_stmt = select(func.count()).select_from(Collection).where(Collection.flat_id == flat_id)
    collection_count = int((await db.execute(count_stmt)).scalar_one())
    if collection_count:
        raise FlatHasCollectionsError(flat.flat_number, collection_count)

    snapshot = audit_service.snapshot_of(flat)
    await db.delete(flat)
    await db.flush()
    await audit_service.record(
        db,
        entity_type=AuditEntity.FLAT,
        entity_id=flat_id,
        action=AuditAction.DELETE,
        before=snapshot,
        actor=actor,
    )
    await db.commit()


async def flat_config_report(db: AsyncSession) -> dict:
    """Explicitly surfaces the 24-vs-28 flat discrepancy."""
    existing_by_wing_stmt = select(Flat.wing, func.count()).group_by(Flat.wing)
    existing_by_wing = {
        wing: int(count) for wing, count in (await db.execute(existing_by_wing_stmt)).all()
    }
    total_existing = sum(existing_by_wing.values())

    wings = [
        {
            "code": wing.code,
            "configured_flat_count": wing.flat_count,
            "existing_flat_count": existing_by_wing.get(wing.code, 0),
        }
        for wing in settings.wings
    ]
    configured = settings.configured_flat_count
    expected = settings.EXPECTED_TOTAL_FLATS
    discrepancy = expected - configured
    matches = discrepancy == 0

    if matches:
        message = f"Flat configuration matches the expected total of {expected} flats."
        how_to_fix: list[str] = []
    else:
        message = (
            f"SOCIETY_WINGS='{settings.SOCIETY_WINGS}' produces {configured} flats "
            f"but EXPECTED_TOTAL_FLATS is {expected} "
            f"({abs(discrepancy)} flat(s) {'missing' if discrepancy > 0 else 'extra'}). "
            "Nothing has been assumed - please confirm the correct structure."
        )
        how_to_fix = [
            "Option 1: extend the existing wings, e.g. SOCIETY_WINGS=A:14,B:14",
            "Option 2: add another wing, e.g. SOCIETY_WINGS=A:12,B:12,C:4",
            "Option 3: if 24 is correct, set EXPECTED_TOTAL_FLATS=24",
            "Then re-run `python -m scripts.seed` (idempotent) or POST /api/flats/bulk",
        ]

    return {
        "wings": wings,
        "configured_flat_count": configured,
        "existing_flat_count": total_existing,
        "expected_total_flats": expected,
        "matches_expectation": matches,
        "discrepancy": discrepancy,
        "message": message,
        "how_to_fix": how_to_fix,
    }
