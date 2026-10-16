from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class WhatsAppJob(Base):
    __tablename__ = "tbwhat"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    def __repr__(self):
        return f"<WhatsAppJob id={self.id} phone_number={self.phone_number!r}>"