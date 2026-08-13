"""Dashboard endpoint — /api/dashboard"""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import DbSession
from app.schemas.common import APIResponse
from app.schemas.dashboard import DashboardResponse
from app.services import finance_service
from app.utils.responses import ERROR_RESPONSES, envelope

router = APIRouter(tags=["Dashboard"], responses=ERROR_RESPONSES)


@router.get(
    "/dashboard",
    response_model=APIResponse[DashboardResponse],
    summary="Everything the Flutter home screen needs, in one call",
    description=(
        "Headline totals, flat participation, payment-method and wing splits, "
        "top expense categories and the most recent transactions. One request "
        "is enough to render the whole dashboard."
    ),
)
async def dashboard(db: DbSession) -> dict:
    data = await finance_service.build_dashboard(db)
    return envelope(DashboardResponse(**data), "Dashboard data fetched successfully")
