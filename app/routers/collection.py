from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from pydantic import BaseModel
from sqlalchemy import Boolean, Numeric, String, bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from sqlalchemy import text

from app.database import get_db
from app.models.api_response import APIResponse
from app.schemas.collection import CollectionCreate, CollectionRead
from app.schemas.email import AprMailCreate
from app.schemas.queue import QueueApprove
from app.sql_loader import load

router = APIRouter(prefix="/collections", tags=["Collections"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_MONEY = Numeric(12, 2, asdecimal=True)
_FLAGS = ("approved", "in_queue", "is_tenant", "is_external")


class CollectionByWingRequest(BaseModel):
    wing: str


class ValidateCodeRequest(BaseModel):
    receiver_phone: str
    transaction_id: str
    passcode: str

_INSERT_COLLECTION = load(
    "collections",
    "insert_collection",
).columns(amount=_MONEY)

_INSERT_QUEUE_ITEM = load(
    "queue",
    "insert_queue_item",
).columns(amount=_MONEY)

_APPROVE_QUEUE_ITEM = load(
    "queue",
    "approve_queue_item",
)

_INSERT_WHATSAPP_JOB = load(
    "whatsapp",
    "insert_whatsapp_job",
)

_INSERT_APR_MAIL = load(
    "email",
    "insert_apr_mail",
)

_VALIDATE_APR_CODE = load(
    "email",
    "validate_apr_code",
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
_USER_BY_EMAIL = text(
    "SELECT admin_access FROM tbuser WHERE email_id = :email_id LIMIT 1"
)
_USER_BY_PHONE = text(
    "SELECT admin_access FROM tbuser WHERE phone_number = :phone_number LIMIT 1"
)

# Fields used as params in each endpoint
_CREATE_REQUIRED = (
    "name",
    "amount",
    "payment_mode",
    "approver_name",
    "approver_phone_number",
    "wing",
    "is_tenant",
    "is_external",
    "phone_number",
    "transaction_id",
    "receiver_name",
    "receiver_phone_number",
)
_UPDATE_QUEUE_REQUIRED = ("name", "phone_number")
_REQUEST_CODE_REQUIRED = (
    "receiver_name",
    "receiver_phone",
    "email_id",
    "is_online",
    "transaction_id",
)
_VALIDATE_CODE_REQUIRED = ("receiver_phone", "transaction_id", "passcode")


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _require_fields(data: dict, fields: tuple[str, ...]) -> None:
    """Raise 400 if any field is missing, null, or a blank string."""
    missing = [
        f for f in fields
        if data.get(f) is None
        or (isinstance(data[f], str) and not data[f].strip())
    ]
    if missing:
        raise _bad_request(f"Missing required field(s): {', '.join(missing)}")


async def _assert_admin_by_email(db: AsyncSession, email_id: str) -> None:
    row = (await db.execute(_USER_BY_EMAIL, {"email_id": email_id.strip()})).first()
    if row is None:
        raise _bad_request(f"email_id '{email_id}' does not exist in tbuser")
    if not row.admin_access:
        raise _bad_request(f"User with email_id '{email_id}' is not an admin")


async def _assert_admin_by_phone(db: AsyncSession, phone: str) -> None:
    row = (await db.execute(_USER_BY_PHONE, {"phone_number": phone.strip()})).first()
    if row is None:
        raise _bad_request(f"receiver_phone '{phone}' does not exist in tbuser")
    if not row.admin_access:
        raise _bad_request(f"User with phone number '{phone}' is not an admin")


def _row_to_read(row):
    return CollectionRead.model_validate(dict(row._mapping))


async def _get_orm_or_404(db, collection_id):
    item = await db.get(CollectionItem, collection_id)

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection {collection_id} does not exist",
        )

    return item

@router.post(
    "/create",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    payload: CollectionCreate,
    db: DbSession,
):
    data = payload.model_dump()

    # All fields used as params must be present
    _require_fields(data, _CREATE_REQUIRED)

    # Tenant name is mandatory when the contributor is a tenant
    if payload.is_tenant:
        _require_fields(data, ("tenant_name",))

    collection_params = {
        "name": payload.name,
        "amount": payload.amount,
        "payment_mode": payload.payment_mode.value,
        "approver_name": payload.approver_name,
        "approver_phone_number": payload.approver_phone_number,
        "wing": payload.wing,
        "is_tenant": payload.is_tenant,
        "is_external": payload.is_external,
        "tenant_name": payload.tenant_name,
        "phone_number": payload.phone_number,
        "transaction_id": payload.transaction_id,
    }

    queue_params = {
        "name": payload.name,
        "phone_number": payload.phone_number,
        "is_tenant": payload.is_tenant,
        "wing": payload.wing,
        "is_external": payload.is_external,
        "amount": payload.amount,
        "payment_mode": payload.payment_mode.value,
        "receiver_name": payload.receiver_name,
        "receiver_phone_number": payload.receiver_phone_number,
    }

    # Both inserts share one transaction: if either fails, neither is saved
    await db.execute(_INSERT_COLLECTION, collection_params)
    await db.execute(_INSERT_QUEUE_ITEM, queue_params)
    await db.commit()

    return APIResponse.created(
        message="Collection created successfully"
    )

@router.get(
    "",
    response_model=APIResponse,
)
async def list_collections(
    db: DbSession,
    response: Response,
    approved: bool | None = Query(None),
    in_queue: bool | None = Query(None),
    is_tenant: bool | None = Query(None),
    is_external: bool | None = Query(None),
    payment_mode: PaymentMode | None = Query(None),
    username: str | None = Query(None),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    search: str | None = Query(None, min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    params = {
        "approved": approved,
        "in_queue": in_queue,
        "is_tenant": is_tenant,
        "is_external": is_external,
        "payment_mode": (
            payment_mode.value
            if payment_mode
            else None
        ),
        "username": username.strip() if username else None,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "search": (
            f"%{search.strip}%"
            if search
            else None
        ),
        "limit": limit,
        "skip": skip,
        "wing": None,
    }

    rows = (
        await db.execute(
            _SELECT_COLLECTIONS,
            params,
        )
    ).all()

    items = [
        _row_to_read(row)
        for row in rows
    ]

    return APIResponse.ok(
        response=items,
        message="Collections fetched successfully",
    )


@router.post(
    "/collection-by-wing",
    response_model=APIResponse,
)
async def select_collection_by_wing(
    request: CollectionByWingRequest,
    db: DbSession,
):
    wing = request.wing.strip()

    rows = (
        await db.execute(
            _SELECT_COLLECTION_BY_WING,
            {
                "wing": wing,
            },
        )
    ).all()

    items = [
        _row_to_read(row)
        for row in rows
    ]

    return APIResponse.ok(
        response=items,
        message="Collections fetched successfully",
    )


@router.get(
    "/total",
    response_model=APIResponse,
)
async def collection_total(
    db: DbSession,
):
    totals = (
        await db.execute(
            _COLLECTION_TOTALS,
        )
    ).one()._mapping

    data = {
        "total_collection": float(
            totals["total_collection"]
        )
    }

    return APIResponse.ok(
        response=data,
        message="Collection total fetched successfully",
    )


@router.get(
    "/top-contributors",
    response_model=APIResponse,
)
async def top_contributors(
    db: DbSession,
    limit: int = Query(10, ge=1, le=100),
):
    rows = (
        await db.execute(
            _TOP_CONTRIBUTORS,
            {"limit": limit},
        )
    ).all()

    items = [
        {
            "name": row.name,
            "total": float(row.total),
            "count": row.count,
        }
        for row in rows
    ]

    return APIResponse.ok(
        response={
            "items": items,
            "total": len(items),
        },
        message="Top contributors fetched successfully",
    )

@router.patch("/update_queue")
async def update_queue(payload: QueueApprove, db: DbSession):
    # Fields used as params must be present
    _require_fields(payload.model_dump(), _UPDATE_QUEUE_REQUIRED)

    result = await db.execute(
        _APPROVE_QUEUE_ITEM,
        {"name": payload.name, "phone_number": payload.phone_number},
    )

    if result.rowcount == 0:
        await db.rollback()
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No pending queue item found for this name and phone number",
        )

    # Commit UPDATE first
    await db.commit()

    # Now create WhatsApp job separately
    await db.execute(
        _INSERT_WHATSAPP_JOB,
        {"name": payload.name, "phone_number": payload.phone_number},
    )
    await db.commit()

    return {
        "message": "Queue item approved",
        "updated": result.rowcount,
    }

@router.post(
    "/request_code",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_code(
    payload: AprMailCreate,
    db: DbSession,
):
    # Fields used as params must be present
    _require_fields(payload.model_dump(), _REQUEST_CODE_REQUIRED)

    # email_id must exist in tbuser and belong to an admin.
    # Kept outside the try/except below so the 400 isn't turned into a 500.
    await _assert_admin_by_email(db, payload.email_id)

    # Temporary hardcoded passcode for testing
    passcode = "12334"

    params = {
        "receiver_name": payload.receiver_name,
        "receiver_phone": payload.receiver_phone,
        "email_id": payload.email_id,
        "is_online": payload.is_online,
        "passcode": passcode,
        "transaction_id": payload.transaction_id,
    }

    try:
        await db.execute(_INSERT_APR_MAIL, params)
        await db.commit()

        return APIResponse.created(
            message="Approval mail request created successfully"
        )

    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create approval mail request",
        )

@router.post(
    "/validate_code",
    response_model=APIResponse,
)
async def validate_code(
    payload: ValidateCodeRequest,
    db: DbSession, 
):
    # Fields used as params must be present
    _require_fields(payload.model_dump(), _VALIDATE_CODE_REQUIRED)

    # receiver_phone must exist in tbuser and belong to an admin
    await _assert_admin_by_phone(db, payload.receiver_phone)

    try:
        result = await db.execute(
            _VALIDATE_APR_CODE,
            {
                "receiver_phone": payload.receiver_phone,
                "transaction_id": payload.transaction_id,
                "passcode": payload.passcode,
            },
        )

        row = result.first()

        # No matching request
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passcode not found",
            )

        # No passcode stored
        if row.passcode is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No passcode available for this approval request",
            )

        # Passcode has expired
        if row.expires_at <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passcode expired",
            )

        # Passcode exists and has not expired
        if row.passcode != payload.passcode:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid passcode",
            )

        return APIResponse.ok(
            message="Passcode validated successfully"
        )

    except HTTPException:
        raise

    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate passcode",
        )