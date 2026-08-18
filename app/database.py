"""Async engine, session factory and the FastAPI session dependency.

`DATABASE_URL` is read from the environment (or `.env`). The driver is
normalised to an async one, so a plain `postgresql://` URL still works and the
test suite can point at `sqlite://` without any other change.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.user import Base

load_dotenv()

DEFAULT_URL = "postgresql+psycopg://ganpati_user:ganpati_password@localhost:5432/ganpati_db"


def _async_url(url: str) -> str:
    """Force an async-capable driver onto whatever DSN we were handed."""
    if url.startswith(("postgresql+psycopg://", "postgresql+asyncpg://")):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):  # Heroku style
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


DATABASE_URL = _async_url(
    os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_URL
)

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "").lower() in {"1", "true", "yes"},
    pool_pre_ping=True,
    future=True,
)

# expire_on_commit=False: without it, touching an attribute after commit
# triggers a lazy refresh, which is fatal inside an async session.
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yields a session per request and always closes it."""
    async with SessionLocal() as session:
        yield session


async def create_tables() -> None:
    """Create any missing table. Alembic remains the tool for real migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    await engine.dispose()
