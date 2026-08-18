"""User endpoints — /api/users (table TBUSER).

Inserts and reads run the statements stored in `sql/queries/users.sql`; the
partial update and delete stay on the ORM, because a PATCH-style update needs
a SET clause built from whichever fields the client actually sent, which a
static .sql file cannot express.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import Boolean, Date, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.sql_loader import load

router = APIRouter(prefix="/users", tags=["Users"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# `dob` is a real date and `admin_access` a real boolean; declaring the types
# lets SQLAlchemy adapt them for whichever driver is in use (the raw sqlite3
# driver cannot bind a Python date on its own).
_INSERT_USER = load("users", "insert_user").bindparams(
    bindparam("dob", type_=Date()), bindparam("admin_access", type_=Boolean())
)
_SELECT_USERS = load("users", "select_users").bindparams(bindparam("admin_access", type_=Boolean()))
_COUNT_USERS = load("users", "count_users").bindparams(bindparam("admin_access", type_=Boolean()))
_SELECT_USER_BY_ID = load("users", "select_user_by_id")
_SELECT_USER_ID_BY_EMAIL = load("users", "select_user_id_by_email")


def _row_to_read(row: Any) -> UserRead:
    return UserRead.model_validate(dict(row._mapping))


async def _get_orm_or_404(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"User {user_id} does not exist")
    return user


# --------------------------------------------------------------- create ----
@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a user row to TBUSER",
    description="Runs the `insert_user` statement from sql/queries/users.sql.",
)
async def create_user(payload: UserCreate, db: DbSession) -> UserRead:
    existing = (await db.execute(_SELECT_USER_ID_BY_EMAIL, {"email_id": payload.email_id})).first()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A user with email_id '{payload.email_id}' already exists"
        )

    row = (await db.execute(_INSERT_USER, payload.model_dump())).one()
    await db.commit()
    return _row_to_read(row)


# ----------------------------------------------------------- retrieval ----
@router.get(
    "",
    response_model=list[UserRead],
    summary="List users",
    description=(
        "Runs `select_users` / `count_users` from sql/queries/users.sql. "
        "The unpaginated match count is returned in the `X-Total-Count` header."
    ),
)
async def list_users(
    db: DbSession,
    response: Response,
    admin_access: bool | None = Query(None, description="Filter by admin flag"),
    search: str | None = Query(None, min_length=1, description="Matches name, email or phone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[UserRead]:
    params = {
        "admin_access": admin_access,
        "search": f"%{search.strip()}%" if search else None,
        "limit": limit,
        "skip": skip,
    }
    rows = (await db.execute(_SELECT_USERS, params)).all()
    total = (await db.execute(_COUNT_USERS, params)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    return [_row_to_read(row) for row in rows]


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get one user",
    description="Runs the `select_user_by_id` statement from sql/queries/users.sql.",
)
async def get_user(db: DbSession, user_id: int = Path(gt=0)) -> UserRead:
    row = (await db.execute(_SELECT_USER_BY_ID, {"id": user_id})).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"User {user_id} does not exist")
    return _row_to_read(row)


# ----------------------------------------------------- update / delete ----
@router.put("/{user_id}", response_model=UserRead, summary="Update a user (partial)")
async def update_user(payload: UserUpdate, db: DbSession, user_id: int = Path(gt=0)) -> UserRead:
    user = await _get_orm_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("email_id") is not None:
        clash = (await db.execute(_SELECT_USER_ID_BY_EMAIL, {"email_id": data["email_id"]})).first()
        if clash is not None and clash.id != user_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"A user with email_id '{data['email_id']}' already exists",
            )
    for field, value in data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_user(db: DbSession, user_id: int = Path(gt=0)) -> Response:
    user = await _get_orm_or_404(db, user_id)
    await db.delete(user)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
