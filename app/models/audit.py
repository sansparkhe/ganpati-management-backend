"""Audit log — requirement #9.

One generic table instead of a history table per entity. Each row records
what changed (`changes` = {field: {old, new}}) plus a full `snapshot` of the
row at that moment, so a deleted record can still be inspected.

Deliberately no foreign keys: audit rows must survive deletion of the entity
they describe.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType
from app.models.enums import AuditAction, AuditEntity, string_enum


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[AuditEntity] = mapped_column(
        string_enum(AuditEntity, "audit_entity"), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[AuditAction] = mapped_column(
        string_enum(AuditAction, "audit_action"), nullable=False
    )
    # {"amount": {"old": "3000.00", "new": "3500.00"}}
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    # Full row state after the change (before the change for DELETE).
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    # Reserved for when authentication is added; NULL until then.
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<AuditLog {self.entity_type}#{self.entity_id} {self.action}>"
