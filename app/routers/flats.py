"""Flat endpoints — /api/flats"""

from __future__ import annotations

from fastapi import APIRouter, Path, Query, status

from app.core.config import settings
from app.dependencies import Actor, DbSession
from app.schemas.collection import FlatCollectionDetail
from app.schemas.common import APIResponse, DeletedResponse
from app.schemas.flat import (
    FlatBulkCreate,
    FlatBulkResult,
    FlatConfigResponse,
    FlatCreate,
    FlatListResponse,
    FlatRead,
    FlatUpdate,
)
from app.services import collection_service, flat_service
from app.utils.responses import ERROR_RESPONSES, envelope

router = APIRouter(prefix="/flats", tags=["Flats"], responses=ERROR_RESPONSES)


@router.get(
    "",
    response_model=APIResponse[FlatListResponse],
    summary="List all flats",
    description=(
        "Returns every flat, ordered A1..A12 then B1..B12. Optional filters: "
        "`wing`, `is_active`, `search`. The list is small (24-28 rows) so it is "
        "not paginated - fetch it once and cache it in the app."
    ),
)
async def list_flats(
    db: DbSession,
    wing: str | None = Query(None, description="Filter by wing, e.g. A"),
    is_active: bool | None = Query(None, description="Only active / inactive flats"),
    search: str | None = Query(None, min_length=1, max_length=60),
) -> dict:
    flats = await flat_service.list_flats(db, wing=wing, is_active=is_active, search=search)
    payload = FlatListResponse(
        items=[FlatRead.model_validate(flat) for flat in flats],
        total=len(flats),
        wings=settings.wing_codes,
    )
    return envelope(payload, "Flats fetched successfully")


@router.get(
    "/config",
    response_model=APIResponse[FlatConfigResponse],
    summary="Flat configuration and the 24 vs 28 discrepancy",
    description=(
        "Reports what SOCIETY_WINGS produces, what actually exists in the "
        "database, and whether it matches EXPECTED_TOTAL_FLATS. Nothing is "
        "assumed - if the numbers disagree this endpoint tells you how to fix it."
    ),
)
async def flat_config(db: DbSession) -> dict:
    report = await flat_service.flat_config_report(db)
    return envelope(FlatConfigResponse(**report), report["message"])


@router.get(
    "/{flat_id}",
    response_model=APIResponse[FlatRead],
    summary="Get one flat",
)
async def get_flat(db: DbSession, flat_id: int = Path(gt=0)) -> dict:
    flat = await flat_service.get_flat(db, flat_id)
    return envelope(FlatRead.model_validate(flat), "Flat fetched successfully")


@router.get(
    "/{flat_id}/collections",
    response_model=APIResponse[FlatCollectionDetail],
    summary="All collections recorded for one flat",
)
async def flat_collections(db: DbSession, flat_id: int = Path(gt=0)) -> dict:
    flat, collections, total = await collection_service.collections_for_flat(db, flat_id)
    payload = FlatCollectionDetail(
        flat=flat,
        total_amount=total,
        collection_count=len(collections),
        collections=collections,
    )
    return envelope(payload, "Flat collections fetched successfully")


@router.post(
    "",
    response_model=APIResponse[FlatRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a flat",
)
async def create_flat(db: DbSession, payload: FlatCreate, actor: Actor) -> dict:
    flat = await flat_service.create_flat(db, payload, actor=actor)
    return envelope(FlatRead.model_validate(flat), f"Flat {flat.flat_number} created successfully")


@router.post(
    "/bulk",
    response_model=APIResponse[FlatBulkResult],
    status_code=status.HTTP_201_CREATED,
    summary="Create several flats at once",
    description="Convenient way to add the remaining flats if the society really has 28.",
)
async def bulk_create_flats(db: DbSession, payload: FlatBulkCreate, actor: Actor) -> dict:
    created, skipped = await flat_service.bulk_create_flats(
        db, payload.flats, skip_existing=payload.skip_existing, actor=actor
    )
    result = FlatBulkResult(
        created=[FlatRead.model_validate(flat) for flat in created],
        skipped=skipped,
        created_count=len(created),
        skipped_count=len(skipped),
    )
    return envelope(result, f"{len(created)} flat(s) created, {len(skipped)} skipped")


@router.put(
    "/{flat_id}",
    response_model=APIResponse[FlatRead],
    summary="Update a flat (partial - send only what changes)",
)
async def update_flat(
    db: DbSession, payload: FlatUpdate, actor: Actor, flat_id: int = Path(gt=0)
) -> dict:
    flat = await flat_service.update_flat(db, flat_id, payload, actor=actor)
    return envelope(FlatRead.model_validate(flat), f"Flat {flat.flat_number} updated successfully")


@router.patch(
    "/{flat_id}",
    response_model=APIResponse[FlatRead],
    summary="Alias of PUT for clients that prefer PATCH",
)
async def patch_flat(
    db: DbSession, payload: FlatUpdate, actor: Actor, flat_id: int = Path(gt=0)
) -> dict:
    return await update_flat(db=db, payload=payload, actor=actor, flat_id=flat_id)


@router.delete(
    "/{flat_id}",
    response_model=APIResponse[DeletedResponse],
    summary="Delete a flat",
    description=(
        "Rejected with 409 FLAT_HAS_COLLECTIONS if any money is recorded against "
        "the flat. Deactivate it instead to keep the financial history intact."
    ),
)
async def delete_flat(db: DbSession, actor: Actor, flat_id: int = Path(gt=0)) -> dict:
    await flat_service.delete_flat(db, flat_id, actor=actor)
    return envelope(DeletedResponse(id=flat_id), "Flat deleted successfully")
