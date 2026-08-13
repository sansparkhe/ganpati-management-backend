"""Audit log endpoints — /api/audit-logs"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.dependencies import DbSession, Pagination
from app.models.enums import AuditAction, AuditEntity
from app.schemas.audit import AuditLogRead
from app.schemas.common import APIResponse, Page
from app.services import audit_service
from app.utils.responses import ERROR_RESPONSES, paginated

router = APIRouter(prefix="/audit-logs", tags=["Audit"], responses=ERROR_RESPONSES)


@router.get(
    "",
    response_model=APIResponse[Page[AuditLogRead]],
    summary="Browse the change history of every financial record",
    description=(
        "Each row records the action, the per-field diff and a full snapshot. "
        "Filter by `entity_type`, `entity_id` and `action`."
    ),
)
async def list_audit_logs(
    db: DbSession,
    pagination: Pagination,
    entity_type: AuditEntity | None = Query(None),
    entity_id: int | None = Query(None, gt=0),
    action: AuditAction | None = Query(None),
) -> dict:
    rows, total = await audit_service.list_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        page=pagination.page,
        limit=pagination.limit,
    )
    return paginated(
        [AuditLogRead.model_validate(row) for row in rows],
        total,
        pagination,
        "Audit logs fetched successfully",
    )
