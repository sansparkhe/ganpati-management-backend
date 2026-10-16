from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, MetaData, Numeric, String, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class QueueItem(Base):
    __tablename__ = "queue_item"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    is_tenant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    wing: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    is_external: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    payment_mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    approver_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    approver_phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    receiver_name: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    receiver_phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    def __repr__(self) -> str:
        return f"<QueueItem id={self.id} name={self.name!r} status={self.status!r}>"