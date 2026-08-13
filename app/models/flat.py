"""Flat (apartment) model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.collection import Collection


class Flat(Base, TimestampMixin):
    __tablename__ = "flats"
    __table_args__ = (
        # Prevents accidental duplicate flat records (requirement #8).
        UniqueConstraint("flat_number", name="uq_flats_flat_number"),
        UniqueConstraint("wing", "display_name", name="uq_flats_wing_display_name"),
        Index("ix_flats_wing", "wing"),
        Index("ix_flats_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wing: Mapped[str] = mapped_column(String(4), nullable=False)
    flat_number: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    # Keeps A2 before A10 (plain string ordering would not).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # `lazy="raise"` on purpose: with an async session a silent lazy load would
    # blow up at serialisation time. Collections are always queried explicitly.
    collections: Mapped[list[Collection]] = relationship(
        back_populates="flat",
        cascade="save-update, merge",
        passive_deletes=True,
        lazy="raise",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Flat id={self.id} number={self.flat_number!r}>"
