"""Collection endpoints — /api/collections (table TBCOLL).

Inserts and reads run the statements stored in `sql/queries/collections.sql`;
the partial update, approve and delete stay on the ORM, because a PATCH-style
update needs a SET clause built from whichever fields the client actually
sent, which a static .sql file cannot express.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import Boolean, Numeric, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.collection import CollectionItem, PaymentMode
from app.schemas.collection import CollectionCreate, CollectionRead, CollectionUpdate
from app.sql_loader import load

router = APIRouter(prefix="/collections", tags=["Collections"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_MONEY = Numeric(12, 2, asdecimal=True)
_FLAGS = ("approved", "in_queue", "is_tenant")

# Money is a Decimal and the flags are real booleans; neither survives the raw
# sqlite3 driver untyped, so the parameters and result column are declared.
_INSERT_COLLECTION = load("collections", "insert_collection").bindparams(
    bindparam("amount", type_=_MONEY), *[bindparam(f, type_=Boolean()) for f in _FLAGS]
)
_SELECT_COLLECTIONS = (
    load("collections", "select_collections")
    .bindparams(
        bindparam("min_amount", type_=_MONEY),
        bindparam("max_amount", type_=_MONEY),
        *[bindparam(f, type_=Boolean()) for f in _FLAGS],
    )
    .columns(amount=_MONEY)
)
_COUNT_COLLECTIONS = load("collections", "count_collections").bindparams(
    bindparam("min_amount", type_=_MONEY),
    bindparam("max_amount", type_=_MONEY),
    *[bindparam(f, type_=Boolean()) for f in _FLAGS],
)
_SELECT_COLLECTION_BY_ID = load("collections", "select_collection_by_id").columns(amount=_MONEY)
_COLLECTION_TOTALS = load("collections", "collection_totals")
_TOTALS_BY_PAYMENT_MODE = load("collections", "collection_totals_by_payment_mode")
_CASH_IN_HAND = load("collections", "collection_cash_in_hand")
_TOP_CONTRIBUTORS = load("collections", "collection_top_contributors")


def _row_to_read(row: Any) -> CollectionRead:
    return CollectionRead.model_validate(dict(row._mapping))


async def _get_orm_or_404(db: AsyncSession, collection_id: int) -> CollectionItem:
    item = await db.get(CollectionItem, collection_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Collection {collection_id} does not exist")
    return item


# --------------------------------------------------------------- create ----
@router.post(
    "",
    response_model=CollectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a collection row to TBCOLL",
    description="Runs the `insert_collection` statement from sql/queries/collections.sql.",
)
async def create_collection(payload: CollectionCreate, db: DbSession) -> CollectionRead:
    params = payload.model_dump()
    params["payment_mode"] = payload.payment_mode.value
    row = (await db.execute(_INSERT_COLLECTION, params)).one()
    await db.commit()
    return _row_to_read(row)


# ----------------------------------------------------------- retrieval ----
@router.get(
    "",
    response_model=list[CollectionRead],
    summary="List collections",
    description=(
        "Runs `select_collections` / `count_collections` from "
        "sql/queries/collections.sql. The unpaginated match count is returned "
        "in the `X-Total-Count` header."
    ),
)
async def list_collections(
    db: DbSession,
    response: Response,
    approved: bool | None = Query(None),
    in_queue: bool | None = Query(None),
    is_tenant: bool | None = Query(None),
    payment_mode: PaymentMode | None = Query(None),
    username: str | None = Query(None, description="Only rows recorded by this user"),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    search: str | None = Query(None, min_length=1, description="Matches owner, tenant or phone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[CollectionRead]:
    params = {
        "approved": approved,
        "in_queue": in_queue,
        "is_tenant": is_tenant,
        "payment_mode": payment_mode.value if payment_mode else None,
        "username": username.strip() if username else None,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "search": f"%{search.strip()}%" if search else None,
        "limit": limit,
        "skip": skip,
    }
    rows = (await db.execute(_SELECT_COLLECTIONS, params)).all()
    total = (await db.execute(_COUNT_COLLECTIONS, params)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    return [_row_to_read(row) for row in rows]


@router.get(
    "/total",
    summary="Approved vs pending totals, payment-mode split and cash in hand",
    description=(
        "Runs `collection_totals`, `collection_totals_by_payment_mode` and "
        "`collection_cash_in_hand` from sql/queries/collections.sql."
    ),
)
async def collection_total(db: DbSession) -> dict:
    totals = (await db.execute(_COLLECTION_TOTALS)).one()._mapping
    by_mode = (await db.execute(_TOTALS_BY_PAYMENT_MODE)).all()
    cash = (await db.execute(_CASH_IN_HAND)).all()
    return {
        # Only approved money counts as collected; the rest is pending.
        "total_collection": float(totals["total_collection"]),
        "collection_count": totals["collection_count"],
        "pending_amount": float(totals["pending_amount"]),
        "pending_count": totals["pending_count"],
        "in_queue_count": totals["in_queue_count"],
        "tenant_payment_count": totals["tenant_payment_count"],
        "total_count": totals["total_count"],
        "by_payment_mode": [
            {
                "payment_mode": row.payment_mode,
                "label": PaymentMode(row.payment_mode).label,
                "total": float(row.total),
                "count": row.count,
            }
            for row in by_mode
        ],
        "cash_in_hand": [
            {"cash_held_by": row.cash_held_by, "total": float(row.total), "count": row.count}
            for row in cash
        ],
    }


@router.get(
    "/top-contributors",
    summary="Who has contributed the most",
    description="Runs `collection_top_contributors` from sql/queries/collections.sql.",
)
async def top_contributors(db: DbSession, limit: int = Query(10, ge=1, le=100)) -> dict:
    rows = (await db.execute(_TOP_CONTRIBUTORS, {"limit": limit})).all()
    return {
        "items": [
            {"owner_name": row.owner_name, "total": float(row.total), "count": row.count}
            for row in rows
        ],
        "total": len(rows),
    }


@router.get(
    "/{collection_id}",
    response_model=CollectionRead,
    summary="Get one collection",
    description="Runs the `select_collection_by_id` statement from sql/queries/collections.sql.",
)
async def get_collection(db: DbSession, collection_id: int = Path(gt=0)) -> CollectionRead:
    row = (await db.execute(_SELECT_COLLECTION_BY_ID, {"id": collection_id})).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Collection {collection_id} does not exist")
    return _row_to_read(row)


# --------------------------------------------- update / approve / delete ----
@router.put("/{collection_id}", response_model=CollectionRead, summary="Update (partial)")
async def update_collection(
    payload: CollectionUpdate, db: DbSession, collection_id: int = Path(gt=0)
) -> CollectionRead:
    item = await _get_orm_or_404(db, collection_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    # Re-check the tenant rule against the merged row, since a partial update
    # can set is_tenant without also sending tenant_name.
    if item.is_tenant and not item.tenant_name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "tenant_name is required when is_tenant is true"
        )
    await db.commit()
    await db.refresh(item)
    return CollectionRead.model_validate(item)


@router.patch("/{collection_id}/approve", response_model=CollectionRead, summary="Approve an item")
async def approve_collection(db: DbSession, collection_id: int = Path(gt=0)) -> CollectionRead:
    item = await _get_orm_or_404(db, collection_id)
    item.approved = True
    item.in_queue = False
    await db.commit()
    await db.refresh(item)
    return CollectionRead.model_validate(item)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_collection(db: DbSession, collection_id: int = Path(gt=0)) -> Response:
    item = await _get_orm_or_404(db, collection_id)
    await db.delete(item)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
