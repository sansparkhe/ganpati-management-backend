from __future__ import annotations
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import Boolean, Date, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.sql_loader import load
from pydantic import BaseModel
from app.utils.crypto_utils import verify_passphrase


router = APIRouter(prefix="/users", tags=["Users"])
DbSession = Annotated[AsyncSession, Depends(get_db)]

_INSERT_USER = load("users", "insert_user").bindparams(
    bindparam("dob", type_=Date()), bindparam("admin_access", type_=Boolean())
)
_SELECT_USERS = load("users", "select_users")
_SELECT_USER_BY_ID = load("users", "select_user_by_id")
_INSERT_REG_MAIL = load("email", "insert_reg_mail").bindparams(
    bindparam("date_of_birth", type_=Date())
)
_VALIDATE_ADMIN = load("users", "validate_admin")
_SELECT_OPEN_LEDGER = load("ledger", "select_open_ledger")
_INSERT_LEDGER = load("ledger", "insert_ledger")
_CLOSE_LEDGER = load("ledger", "close_ledger")
_INSERT_EXPENSES_HISTORY = load("ledger", "insert_expenses_history")
_INSERT_COLLECTIONS_HISTORY = load("ledger", "insert_collections_history")

# Counts tbcoll rows that are not yet approved, i.e. receiver details missing.
# NULL and blank strings both count as "not approved".
_COUNT_UNAPPROVED_COLLECTIONS = text(
    """
    SELECT COUNT(*) AS pending
    FROM tbcoll
    WHERE receiver_name IS NULL
       OR TRIM(receiver_name) = ''
       OR receiver_phone_number IS NULL
       OR TRIM(receiver_phone_number) = ''
    """
)


class InitiatorValidate(BaseModel):
    initiator_name: str
    initiator_number: str


class LedgerInitiate(BaseModel):
    initiator_name: str
    initiator_phone: str

class PassphraseValidate(BaseModel):
    encrypted_passphrase: str

    
def _row_to_read(row):
    return UserRead.model_validate(dict(row._mapping))


async def _get_orm_or_404(db, user_id):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"User {user_id} does not exist")
    return user


@router.post("/create_user", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DbSession):
    existing = (
        await db.execute(
            _SELECT_USER_ID_BY_EMAIL,
            {"email_id": payload.email_id},
        )
    ).first()

    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A user with email_id '{payload.email_id}' already exists",
        )

    # 1. Insert user
    await db.execute(
        _INSERT_USER,
        payload.model_dump(),
    )

    # 2. Insert registration mail entry
    # tbregmail.phone_number is NOT NULL, so only insert when a phone was given
    if payload.phone_number is not None:
        await db.execute(
            _INSERT_REG_MAIL,
            {
                "phone_number": payload.phone_number,
                "first_name": payload.first_name,
                "last_name": payload.last_name,
                "email_id": payload.email_id,
                "date_of_birth": payload.dob.isoformat() if payload.dob else None,
            },
        )

    # One commit for both inserts: if either fails, neither is saved
    await db.commit()

    # ... the rest of your existing code (fetch the user and return it) stays unchanged

    # Get the newly inserted user's ID
    result = await db.execute(
        text("SELECT LAST_INSERT_ID() AS id")
    )
    user_id = result.scalar_one()

    # Fetch the complete user
    result = await db.execute(
        _SELECT_USER_BY_ID,
        {"id": user_id},
    )

    row = result.first()
    if row is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "User was inserted but could not be retrieved",
        )

    return _row_to_read(row)


@router.get("", response_model=list[UserRead])
async def list_users(
    db: DbSession,
):
    rows = (await db.execute(_SELECT_USERS)).all()
    return [_row_to_read(row) for row in rows]


@router.put("/validate_initiator")
async def validate_initiator(payload: InitiatorValidate, db: DbSession):
    row = (
        await db.execute(
            _VALIDATE_ADMIN,
            {"initiator_name": payload.initiator_name, "initiator_number": payload.initiator_number},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User not found")
    if not row.admin_access:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User does not have admin access")
    return {"is_admin": True}


@router.put("/initiate_ledger", status_code=status.HTTP_201_CREATED)
async def initiate_ledger(payload: LedgerInitiate, db: DbSession):
    open_row = (await db.execute(_SELECT_OPEN_LEDGER)).first()
    if open_row is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"year": open_row.year, "message": "Ledger is already open"},
        )

    year = date.today().year
    try:
        await db.execute(
            _INSERT_LEDGER,
            {"year": year, "initiator_name": payload.initiator_name, "initiator_phone": payload.initiator_phone},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"year": year, "message": "A ledger record already exists for this year"},
        )
    return {"year": year, "message": "Ledger initiated successfully"}


@router.put("/close_ledger")
async def close_ledger(db: DbSession):
    open_row = (await db.execute(_SELECT_OPEN_LEDGER)).first()
    if open_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No open ledger found")

    # The ledger can only be closed once every collection has been approved
    # (receiver_name and receiver_phone_number are filled in).
    pending = (await db.execute(_COUNT_UNAPPROVED_COLLECTIONS)).scalar_one()
    if pending > 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot close ledger: {pending} collection record(s) are not yet approved",
        )

    params = {"year": open_row.year}
    try:
        await db.execute(_INSERT_COLLECTIONS_HISTORY, params)
        await db.execute(_INSERT_EXPENSES_HISTORY, params)
        await db.execute(_CLOSE_LEDGER, params)
        await db.commit()
    except Exception as e:
        print(e)
        await db.rollback()
        raise

    return {"year": open_row.year, "message": "Ledger closed and mirrored"}


@router.put("/validate")
async def validate(payload: PassphraseValidate):
    if not verify_passphrase(payload.encrypted_passphrase):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid passphrase")
    return {"valid": True, "message": "Passphrase validated"}