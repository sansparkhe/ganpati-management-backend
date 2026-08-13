"""Test fixtures.

The suite runs against a throwaway in-memory SQLite database, so it never
touches development or production data and needs no PostgreSQL server. The
models use portable types (VARCHAR-backed enums, JSON with a JSONB variant)
specifically so this works.

To run the suite against real PostgreSQL instead:

    TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ganpati_test pytest
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import date, timedelta

os.environ.setdefault("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SOCIETY_WINGS", "A:12,B:12")
os.environ.setdefault("EXPECTED_TOTAL_FLATS", "28")
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.flat import Flat  # noqa: E402
from app.services import category_service  # noqa: E402
from app.services.flat_service import derive_sort_order  # noqa: E402

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
async def engine():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # SQLite ignores foreign keys unless asked; PostgreSQL always enforces them.
    @event.listens_for(test_engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def session_factory(engine):
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.fixture
async def categories(db):
    """The 10 default expense categories."""
    return await category_service.ensure_default_categories(db)


@pytest.fixture
async def flats(db):
    """Flats A1..A12 and B1..B12, exactly as the seed script creates them."""
    created = []
    for wing in settings.wings:
        for index in range(1, wing.flat_count + 1):
            number = f"{wing.code}{index}"
            flat = Flat(
                wing=wing.code,
                flat_number=number,
                display_name=number,
                sort_order=derive_sort_order(wing.code, number),
            )
            db.add(flat)
            created.append(flat)
    await db.commit()
    for flat in created:
        await db.refresh(flat)
    return created


@pytest.fixture
async def seeded(flats, categories):
    """Reference data only — no transactions, so every test starts at zero."""
    return {"flats": flats, "categories": categories}


def data_of(response) -> dict:
    """Unwrap the {success, data, message} envelope."""
    body = response.json()
    assert body["success"] is True, body
    return body["data"]


def error_of(response) -> dict:
    body = response.json()
    assert body["success"] is False, body
    return body
