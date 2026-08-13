"""Metadata + health endpoints.

`GET /api/meta` is the first call a Flutter app should make: it returns every
dropdown value (payment methods, statuses, wings, categories) in one request.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.dependencies import DbSession
from app.models.enums import CollectionStatus, PaymentMethod
from app.schemas.category import ExpenseCategoryRead
from app.schemas.common import APIResponse
from app.schemas.meta import EnumOption, HealthResponse, MetaResponse
from app.services import category_service
from app.utils.responses import envelope

router = APIRouter(tags=["Meta"])

_STATUS_LABELS = {
    CollectionStatus.PENDING: "Pending",
    CollectionStatus.CONFIRMED: "Confirmed",
    CollectionStatus.CANCELLED: "Cancelled",
}


@router.get(
    "/meta",
    response_model=APIResponse[MetaResponse],
    summary="Enums, wings and categories for the app's dropdowns",
)
async def meta(db: DbSession) -> dict:
    categories = await category_service.list_categories(db, is_active=True)
    payload = MetaResponse(
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        currency=settings.CURRENCY_CODE,
        currency_symbol=settings.CURRENCY_SYMBOL,
        payment_methods=[
            EnumOption(value=method.value, label=method.label) for method in PaymentMethod
        ],
        collection_statuses=[
            EnumOption(value=status.value, label=_STATUS_LABELS[status])
            for status in CollectionStatus
        ],
        wings=settings.wing_codes,
        expense_categories=[ExpenseCategoryRead.model_validate(row) for row in categories],
        default_page_size=settings.DEFAULT_PAGE_SIZE,
        max_page_size=settings.MAX_PAGE_SIZE,
    )
    return envelope(payload, "Metadata fetched successfully")


@router.get(
    "/health",
    response_model=APIResponse[HealthResponse],
    summary="Liveness probe including a real database round trip",
)
async def health(db: DbSession) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        database = "connected"
    except Exception:  # pragma: no cover - only hit when the DB is down
        database = "unavailable"

    payload = HealthResponse(
        status="ok" if database == "connected" else "degraded",
        database=database,
        environment=settings.APP_ENV,
        version=settings.APP_VERSION,
    )
    return envelope(
        payload, "Service is healthy" if database == "connected" else "Database is unreachable"
    )
