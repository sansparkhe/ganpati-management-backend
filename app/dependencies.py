"""Reusable FastAPI dependencies: DB session, pagination, actor and filters."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.enums import AuditAction, AuditEntity, CollectionStatus, PaymentMethod
from app.services.collection_service import CollectionFilters
from app.services.expense_service import ExpenseFilters
from app.utils.pagination import PaginationParams

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_pagination(
    page: int = Query(1, ge=1, description="1-based page number"),
    limit: int = Query(
        default=settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description=f"Items per page (max {settings.MAX_PAGE_SIZE})",
    ),
) -> PaginationParams:
    return PaginationParams(page=page, limit=limit)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]


def get_actor(
    x_actor: Annotated[
        str | None,
        Header(
            alias="X-Actor",
            description=(
                "Optional name of the person performing the action; stored in the "
                "audit log. Replaced by the authenticated user once auth is added."
            ),
        ),
    ] = None,
) -> str | None:
    return x_actor.strip()[:120] if x_actor and x_actor.strip() else None


Actor = Annotated[str | None, Depends(get_actor)]


def get_collection_filters(
    flat_id: int | None = Query(None, gt=0, description="Only this flat's collections"),
    wing: str | None = Query(None, description="Filter by wing, e.g. A"),
    payment_method: PaymentMethod | None = Query(None),
    status: CollectionStatus | None = Query(None),
    date_from: date | None = Query(None, description="Inclusive lower bound on collected_on"),
    date_to: date | None = Query(None, description="Inclusive upper bound on collected_on"),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    search: str | None = Query(
        None, min_length=1, max_length=100, description="Matches notes, reference, flat, owner"
    ),
) -> CollectionFilters:
    return CollectionFilters(
        flat_id=flat_id,
        wing=wing,
        payment_method=payment_method,
        status=status,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )


CollectionFilterParams = Annotated[CollectionFilters, Depends(get_collection_filters)]


def get_expense_filters(
    category_id: int | None = Query(None, gt=0),
    category: str | None = Query(
        None, description="Category code, e.g. DECORATION", alias="category"
    ),
    payment_method: PaymentMethod | None = Query(None),
    date_from: date | None = Query(None, description="Inclusive lower bound on spent_on"),
    date_to: date | None = Query(None, description="Inclusive upper bound on spent_on"),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    search: str | None = Query(
        None, min_length=1, max_length=100, description="Matches title, vendor, notes, reference"
    ),
) -> ExpenseFilters:
    return ExpenseFilters(
        category_id=category_id,
        category_code=category,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )


ExpenseFilterParams = Annotated[ExpenseFilters, Depends(get_expense_filters)]

__all__ = [
    "Actor",
    "AuditAction",
    "AuditEntity",
    "CollectionFilterParams",
    "DbSession",
    "ExpenseFilterParams",
    "Pagination",
]
