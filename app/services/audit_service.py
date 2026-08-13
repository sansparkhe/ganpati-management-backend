"""Audit trail helpers.

Services call `record()` after every create/update/delete of a financial
record. The diff is computed from plain dictionaries so the same code works
for any model.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditAction, AuditEntity

# Never treated as a meaningful change by itself.
_IGNORED_FIELDS = {"created_at", "updated_at"}


def _jsonable(value: Any) -> Any:
    """Convert a column value into something JSON/JSONB can store."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        # Quantise so 2500 and 2500.00 compare equal in the diff, and never
        # convert to float — audit values stay exact strings.
        return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def snapshot_of(instance: Any) -> dict[str, Any]:
    """Dump every mapped column of an ORM instance to a JSON-safe dict.

    Reads the already-loaded state instead of using `getattr`, so it can never
    trigger a lazy refresh (which would be illegal inside an async session).
    """
    state = inspect(instance)
    loaded = state.dict
    return {
        attr.key: _jsonable(loaded[attr.key])
        for attr in state.mapper.column_attrs
        if attr.key in loaded
    }


def diff(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    """Per-field `{old, new}` map of everything that actually changed."""
    before = before or {}
    after = after or {}
    changes: dict[str, Any] = {}
    for key in set(before) | set(after):
        if key in _IGNORED_FIELDS:
            continue
        old_value = before.get(key)
        new_value = after.get(key)
        if old_value != new_value:
            changes[key] = {"old": old_value, "new": new_value}
    return changes


async def record(
    db: AsyncSession,
    *,
    entity_type: AuditEntity,
    entity_id: int,
    action: AuditAction,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    actor: str | None = None,
    note: str | None = None,
) -> AuditLog | None:
    """Write one audit row.

    Returns None for UPDATEs that changed nothing, so the log stays signal.
    The caller is responsible for committing.
    """
    changes = diff(before, after) if action is AuditAction.UPDATE else None
    if action is AuditAction.UPDATE and not changes:
        return None

    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=changes,
        snapshot=after if action is not AuditAction.DELETE else before,
        actor=actor,
        note=note,
    )
    db.add(entry)
    return entry


async def history_for(
    db: AsyncSession,
    *,
    entity_type: AuditEntity,
    entity_id: int,
    limit: int = 100,
) -> Sequence[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def list_logs(
    db: AsyncSession,
    *,
    entity_type: AuditEntity | None = None,
    entity_id: int | None = None,
    action: AuditAction | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[Sequence[AuditLog], int]:
    from sqlalchemy import func

    conditions = []
    if entity_type is not None:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        conditions.append(AuditLog.entity_id == entity_id)
    if action is not None:
        conditions.append(AuditLog.action == action)

    count_stmt = select(func.count()).select_from(AuditLog)
    list_stmt = select(AuditLog)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)

    total = int((await db.execute(count_stmt)).scalar_one())
    list_stmt = (
        list_stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = (await db.execute(list_stmt)).scalars().all()
    return rows, total
