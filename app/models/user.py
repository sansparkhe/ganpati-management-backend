"""User model.

This module also holds the shared declarative `Base` and the `MoneyType`
column type, because the models package is deliberately limited to three
files — `user.py`, `expense.py` and `collection.py` — so there is no separate
`base.py` for them to live in. `expense.py` and `collection.py` import from
here; this module imports from neither, so the dependency runs one way only.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, MetaData, Numeric, String, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names keep Alembic migrations readable and let
# constraints be dropped by name later.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# NUMERIC(12, 2): up to 9,999,999,999.99, held as Decimal — never a float.
MoneyType = Numeric(12, 2, asdecimal=True)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class User(Base):
    __tablename__ = "TBUSER"

    id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dob: Mapped[date | None] = mapped_column("dob", Date, nullable=True)
    email_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    admin_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false(), index=True
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User id={self.id} email_id={self.email_id!r}>"
