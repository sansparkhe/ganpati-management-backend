"""Declarative base, shared column types and mixins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, MetaData, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names make Alembic migrations readable and allow
# constraints to be dropped by name later.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# NUMERIC(12, 2): up to 9,999,999,999.99 — never a float, never a Python float.
MoneyType = Numeric(12, 2, asdecimal=True)

# JSONB on PostgreSQL, plain JSON elsewhere (the test suite runs on SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    """Adds `created_at` / `updated_at` to a model (audit requirement #9).

    The values are generated in Python (`default`/`onupdate`) with a matching
    `server_default` as a database-level safety net. Using a SQL expression for
    `onupdate` would expire the attribute after every flush, which would force
    an extra lazy load — fatal inside an async session.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
