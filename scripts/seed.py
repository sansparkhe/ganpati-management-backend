"""Seed script.

    python -m scripts.seed                  # flats + expense categories
    python -m scripts.seed --with-samples   # + sample collections and expenses
    python -m scripts.seed --reset          # wipe transactional data first

=============================================================================
 FLAT COUNT NOTICE — please read
=============================================================================
The default SOCIETY_WINGS="A:12,B:12" creates 24 flats: A1..A12 and B1..B12.
The original requirement mentions 28 flats. This script does NOT guess which
is correct — it creates exactly what SOCIETY_WINGS says and prints a warning
when that differs from EXPECTED_TOTAL_FLATS.

To add the remaining 4 flats later, edit .env:

    SOCIETY_WINGS=A:14,B:14        -> A1..A14, B1..B14   (28 flats)
    SOCIETY_WINGS=A:12,B:12,C:4    -> adds a C wing      (28 flats)

then re-run this script. It is idempotent: existing flats are left untouched
and only the missing ones are inserted.
=============================================================================
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.database import SessionLocal, dispose_engine
from app.models.audit import AuditLog
from app.models.category import ExpenseCategory
from app.models.collection import Collection
from app.models.enums import CollectionStatus, PaymentMethod
from app.models.expense import Expense
from app.models.flat import Flat
from app.services import category_service
from app.services.flat_service import derive_sort_order

SAMPLE_COLLECTIONS = [
    # (flat_number, amount, method, days_ago, notes)
    ("A1", "2500", PaymentMethod.UPI, 6, "Ganpati contribution"),
    ("A2", "2500", PaymentMethod.CASH, 6, None),
    ("A3", "5000", PaymentMethod.BANK_TRANSFER, 5, "Extra donation"),
    ("A4", "2500", PaymentMethod.UPI, 5, None),
    ("A5", "1500", PaymentMethod.CASH, 4, "Partial - balance promised"),
    ("B1", "2500", PaymentMethod.UPI, 4, None),
    ("B2", "3000", PaymentMethod.UPI, 3, None),
    ("B3", "2500", PaymentMethod.CASH, 3, None),
    ("B4", "2500", PaymentMethod.OTHER, 2, "Cheque no 100234"),
]

SAMPLE_EXPENSES = [
    # (title, amount, method, category_code, days_ago, vendor)
    ("Decoration material", "3500", PaymentMethod.UPI, "DECORATION", 5, "Sai Decorators"),
    ("Mandap rent", "6000", PaymentMethod.BANK_TRANSFER, "DECORATION", 5, "Balaji Mandap"),
    ("Sound system rental", "4500", PaymentMethod.CASH, "SOUND", 4, "Ganesh Sound"),
    ("Modak prasad", "1800", PaymentMethod.CASH, "PRASAD", 3, "Chitale Sweets"),
    ("Pooja saman", "1200", PaymentMethod.UPI, "POOJA", 3, None),
    ("Tempo for idol", "900", PaymentMethod.CASH, "TRANSPORTATION", 2, None),
]


async def seed_flats(session) -> tuple[int, int]:
    """Create every flat implied by SOCIETY_WINGS. Idempotent."""
    existing = {number for (number,) in (await session.execute(select(Flat.flat_number))).all()}
    created = 0
    for wing in settings.wings:
        for index in range(1, wing.flat_count + 1):
            flat_number = f"{wing.code}{index}"
            if flat_number in existing:
                continue
            session.add(
                Flat(
                    wing=wing.code,
                    flat_number=flat_number,
                    display_name=flat_number,
                    is_active=True,
                    sort_order=derive_sort_order(wing.code, flat_number),
                )
            )
            created += 1
    await session.commit()
    total = int((await session.execute(select(func.count(Flat.id)))).scalar_one())
    return created, total


async def seed_samples(session) -> tuple[int, int]:
    flats = {
        number: flat_id
        for flat_id, number in (await session.execute(select(Flat.id, Flat.flat_number))).all()
    }
    categories = {
        code: category_id
        for category_id, code in (
            await session.execute(select(ExpenseCategory.id, ExpenseCategory.code))
        ).all()
    }
    today = date.today()

    existing_collections = int(
        (await session.execute(select(func.count(Collection.id)))).scalar_one()
    )
    collections_added = 0
    if existing_collections == 0:
        for flat_number, amount, method, days_ago, notes in SAMPLE_COLLECTIONS:
            flat_id = flats.get(flat_number)
            if flat_id is None:
                continue
            session.add(
                Collection(
                    flat_id=flat_id,
                    amount=Decimal(amount),
                    payment_method=method,
                    status=CollectionStatus.CONFIRMED,
                    collected_on=today - timedelta(days=days_ago),
                    notes=notes,
                )
            )
            collections_added += 1

    existing_expenses = int((await session.execute(select(func.count(Expense.id)))).scalar_one())
    expenses_added = 0
    if existing_expenses == 0:
        for title, amount, method, code, days_ago, vendor in SAMPLE_EXPENSES:
            category_id = categories.get(code)
            if category_id is None:
                continue
            session.add(
                Expense(
                    category_id=category_id,
                    title=title,
                    amount=Decimal(amount),
                    payment_method=method,
                    spent_on=today - timedelta(days=days_ago),
                    vendor=vendor,
                )
            )
            expenses_added += 1

    await session.commit()
    return collections_added, expenses_added


async def reset_transactions(session) -> None:
    await session.execute(delete(Collection))
    await session.execute(delete(Expense))
    await session.execute(delete(AuditLog))
    await session.commit()


async def main(with_samples: bool, reset: bool) -> None:
    async with SessionLocal() as session:
        if reset:
            await reset_transactions(session)
            print("Cleared collections, expenses and audit logs.")

        categories = await category_service.ensure_default_categories(session)
        print(f"Expense categories: {len(categories)} created (existing ones untouched).")

        created, total = await seed_flats(session)
        print(f"Flats: {created} created, {total} total in the database.")

        if with_samples:
            collections_added, expenses_added = await seed_samples(session)
            print(
                f"Sample data: {collections_added} collection(s), "
                f"{expenses_added} expense(s) added."
            )

    print("-" * 74)
    print(f"SOCIETY_WINGS = {settings.SOCIETY_WINGS} -> {settings.configured_flat_count} flats")
    if not settings.flat_count_matches_expectation:
        missing = settings.EXPECTED_TOTAL_FLATS - settings.configured_flat_count
        print(
            f"WARNING: the requirement says {settings.EXPECTED_TOTAL_FLATS} flats but the "
            f"configuration produces {settings.configured_flat_count} "
            f"({abs(missing)} {'missing' if missing > 0 else 'extra'})."
        )
        print("         Nothing was assumed. To add the remaining flats set one of:")
        print("           SOCIETY_WINGS=A:14,B:14      (A1..A14, B1..B14)")
        print("           SOCIETY_WINGS=A:12,B:12,C:4  (adds a C wing)")
        print("         then re-run: python -m scripts.seed")
        print("         If 24 is actually correct, set EXPECTED_TOTAL_FLATS=24.")
    else:
        print(f"Flat count matches EXPECTED_TOTAL_FLATS ({settings.EXPECTED_TOTAL_FLATS}).")
    print("-" * 74)

    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Ganpati database")
    parser.add_argument(
        "--with-samples",
        action="store_true",
        help="Also insert sample collections and expenses for development",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all collections, expenses and audit logs before seeding",
    )
    args = parser.parse_args()
    asyncio.run(main(args.with_samples, args.reset))
