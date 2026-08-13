"""Expense category endpoints — /api/expense-categories"""

from __future__ import annotations

from fastapi import APIRouter, Path, Query, status

from app.dependencies import Actor, DbSession
from app.schemas.category import (
    CategoryListResponse,
    ExpenseCategoryCreate,
    ExpenseCategoryRead,
    ExpenseCategoryUpdate,
)
from app.schemas.common import APIResponse, DeletedResponse
from app.services import category_service
from app.utils.responses import ERROR_RESPONSES, envelope

router = APIRouter(
    prefix="/expense-categories", tags=["Expense Categories"], responses=ERROR_RESPONSES
)


@router.get(
    "",
    response_model=APIResponse[CategoryListResponse],
    summary="List expense categories",
    description="Use `code` (e.g. DECORATION) when filtering expenses; it never changes.",
)
async def list_categories(
    db: DbSession,
    is_active: bool | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=60),
) -> dict:
    categories = await category_service.list_categories(db, is_active=is_active, search=search)
    payload = CategoryListResponse(
        items=[ExpenseCategoryRead.model_validate(row) for row in categories],
        total=len(categories),
    )
    return envelope(payload, "Expense categories fetched successfully")


@router.get(
    "/{category_id}",
    response_model=APIResponse[ExpenseCategoryRead],
    summary="Get one expense category",
)
async def get_category(db: DbSession, category_id: int = Path(gt=0)) -> dict:
    category = await category_service.get_category(db, category_id)
    return envelope(
        ExpenseCategoryRead.model_validate(category), "Expense category fetched successfully"
    )


@router.post(
    "",
    response_model=APIResponse[ExpenseCategoryRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create an expense category",
)
async def create_category(db: DbSession, payload: ExpenseCategoryCreate, actor: Actor) -> dict:
    category = await category_service.create_category(db, payload, actor=actor)
    return envelope(
        ExpenseCategoryRead.model_validate(category),
        f"Expense category '{category.code}' created successfully",
    )


@router.put(
    "/{category_id}",
    response_model=APIResponse[ExpenseCategoryRead],
    summary="Update an expense category (partial)",
    description="`code` is immutable on purpose - it is the stable key clients filter on.",
)
async def update_category(
    db: DbSession, payload: ExpenseCategoryUpdate, actor: Actor, category_id: int = Path(gt=0)
) -> dict:
    category = await category_service.update_category(db, category_id, payload, actor=actor)
    return envelope(
        ExpenseCategoryRead.model_validate(category), "Expense category updated successfully"
    )


@router.delete(
    "/{category_id}",
    response_model=APIResponse[DeletedResponse],
    summary="Delete an expense category",
    description="Rejected with 409 CATEGORY_IN_USE when expenses still reference it.",
)
async def delete_category(db: DbSession, actor: Actor, category_id: int = Path(gt=0)) -> dict:
    await category_service.delete_category(db, category_id, actor=actor)
    return envelope(DeletedResponse(id=category_id), "Expense category deleted successfully")
