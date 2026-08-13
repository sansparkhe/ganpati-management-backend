"""Collection endpoints — /api/collections"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Path, Query, status

from app.dependencies import Actor, CollectionFilterParams, DbSession, Pagination
from app.models.enums import AuditEntity
from app.schemas.audit import AuditHistoryResponse, AuditLogRead
from app.schemas.collection import (
    CollectionCreate,
    CollectionRead,
    CollectionSummary,
    CollectionUpdate,
    FlatContributionListResponse,
    PendingFlatsResponse,
)
from app.schemas.common import APIResponse, DeletedResponse, Page
from app.services import audit_service, collection_service
from app.utils.responses import ERROR_RESPONSES, envelope, paginated

router = APIRouter(prefix="/collections", tags=["Collections"], responses=ERROR_RESPONSES)


@router.get(
    "",
    response_model=APIResponse[Page[CollectionRead]],
    summary="List collections (paginated + filterable)",
    description=(
        "Filters: `flat_id`, `wing`, `payment_method`, `status`, `date_from`, "
        "`date_to`, `min_amount`, `max_amount`, `search`. "
        "Pagination: `page` (1-based) and `limit`."
    ),
)
async def list_collections(
    db: DbSession, filters: CollectionFilterParams, pagination: Pagination
) -> dict:
    rows, total = await collection_service.list_collections(db, filters, pagination)
    return paginated(
        [CollectionRead.model_validate(row) for row in rows],
        total,
        pagination,
        "Collections fetched successfully",
    )


@router.get(
    "/summary",
    response_model=APIResponse[CollectionSummary],
    summary="Collection summary (totals, by wing, by flat, by payment method)",
    description=(
        "All numbers are computed from the individual transactions. Only "
        "CONFIRMED collections count towards `total_collection`; PENDING is "
        "reported separately and CANCELLED is excluded."
    ),
)
async def collection_summary(
    db: DbSession,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> dict:
    summary = await collection_service.build_summary(db, date_from=date_from, date_to=date_to)
    return envelope(CollectionSummary(**summary), "Collection summary generated successfully")


@router.get(
    "/by-flat",
    response_model=APIResponse[FlatContributionListResponse],
    summary="How much each flat has contributed",
)
async def collections_by_flat(
    db: DbSession,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> dict:
    rows = await collection_service.contributions_by_flat(db, date_from=date_from, date_to=date_to)
    payload = FlatContributionListResponse(items=rows, total=len(rows))
    return envelope(payload, "Per-flat contributions fetched successfully")


@router.get(
    "/pending-flats",
    response_model=APIResponse[PendingFlatsResponse],
    summary="Flats that have not contributed yet",
)
async def pending_flats(db: DbSession) -> dict:
    flats = await collection_service.pending_flats(db)
    payload = PendingFlatsResponse(items=flats, total=len(flats))
    return envelope(payload, f"{len(flats)} flat(s) have not contributed yet")


@router.get(
    "/{collection_id}",
    response_model=APIResponse[CollectionRead],
    summary="Get one collection",
)
async def get_collection(db: DbSession, collection_id: int = Path(gt=0)) -> dict:
    collection = await collection_service.get_collection(db, collection_id)
    return envelope(CollectionRead.model_validate(collection), "Collection fetched successfully")


@router.get(
    "/{collection_id}/history",
    response_model=APIResponse[AuditHistoryResponse],
    summary="Audit trail for one collection",
)
async def collection_history(db: DbSession, collection_id: int = Path(gt=0)) -> dict:
    await collection_service.get_collection(db, collection_id)
    logs = await audit_service.history_for(
        db, entity_type=AuditEntity.COLLECTION, entity_id=collection_id
    )
    payload = AuditHistoryResponse(
        entity_type=AuditEntity.COLLECTION,
        entity_id=collection_id,
        items=[AuditLogRead.model_validate(log) for log in logs],
        total=len(logs),
    )
    return envelope(payload, "Collection history fetched successfully")


@router.post(
    "",
    response_model=APIResponse[CollectionRead],
    status_code=status.HTTP_201_CREATED,
    summary="Record a contribution for a flat",
    description="Fails with 404 FLAT_NOT_FOUND if `flat_id` does not exist.",
)
async def create_collection(db: DbSession, payload: CollectionCreate, actor: Actor) -> dict:
    collection = await collection_service.create_collection(db, payload, actor=actor)
    return envelope(CollectionRead.model_validate(collection), "Collection created successfully")


@router.put(
    "/{collection_id}",
    response_model=APIResponse[CollectionRead],
    summary="Update a collection (partial - send only what changes)",
    description="Every change is written to the audit log; pass `audit_note` to record why.",
)
async def update_collection(
    db: DbSession, payload: CollectionUpdate, actor: Actor, collection_id: int = Path(gt=0)
) -> dict:
    collection = await collection_service.update_collection(db, collection_id, payload, actor=actor)
    return envelope(CollectionRead.model_validate(collection), "Collection updated successfully")


@router.patch(
    "/{collection_id}",
    response_model=APIResponse[CollectionRead],
    summary="Alias of PUT for clients that prefer PATCH",
)
async def patch_collection(
    db: DbSession, payload: CollectionUpdate, actor: Actor, collection_id: int = Path(gt=0)
) -> dict:
    return await update_collection(db=db, payload=payload, actor=actor, collection_id=collection_id)


@router.delete(
    "/{collection_id}",
    response_model=APIResponse[DeletedResponse],
    summary="Delete a collection",
    description="The deleted row is preserved in the audit log as a snapshot.",
)
async def delete_collection(
    db: DbSession,
    actor: Actor,
    collection_id: int = Path(gt=0),
    reason: str | None = Query(None, max_length=500, description="Stored in the audit log"),
) -> dict:
    await collection_service.delete_collection(db, collection_id, actor=actor, note=reason)
    return envelope(DeletedResponse(id=collection_id), "Collection deleted successfully")
