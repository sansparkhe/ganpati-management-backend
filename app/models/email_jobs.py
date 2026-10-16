from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class RegMail(Base):
    __tablename__ = "tbregmail"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    email_id: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    date_of_birth: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    created_ts: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    completed_ts: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    def __repr__(self):
        return f"<RegMail id={self.id} phone_number={self.phone_number!r}>"


class AprMail(Base):
    __tablename__ = "tbaprmail"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    approver_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    approver_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    is_online: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
    )

    email_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=False,
    )

    passcode: Mapped[str] = mapped_column(
        String(20), 
        nullable=False,
    )

    transaction_id: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    expires_at: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )   

    created_ts: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    completed_ts: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    def __repr__(self):
        return f"<AprMail id={self.id} transaction_id={self.transaction_id!r}>"