"""Audit log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AuditAction, AuditEntity
from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: int
    entity_type: AuditEntity
    entity_id: int
    action: AuditAction
    changes: dict[str, Any] | None = Field(
        default=None,
        description='Per-field diff, e.g. {"amount": {"old": "3000.00", "new": "3500.00"}}',
    )
    snapshot: dict[str, Any] | None = Field(
        default=None, description="Full row state after the change (before it, for DELETE)"
    )
    actor: str | None = None
    note: str | None = None
    created_at: datetime


class AuditHistoryResponse(BaseModel):
    entity_type: AuditEntity
    entity_id: int
    items: list[AuditLogRead]
    total: int
