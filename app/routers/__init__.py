"""Every router, assembled onto one API router mounted at settings.API_PREFIX."""

from fastapi import APIRouter

from app.routers import (
    audit,
    categories,
    collections,
    dashboard,
    expenses,
    finance,
    flats,
    meta,
)

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(dashboard.router)
api_router.include_router(flats.router)
api_router.include_router(collections.router)
api_router.include_router(expenses.router)
api_router.include_router(categories.router)
api_router.include_router(finance.router)
api_router.include_router(audit.router)

__all__ = ["api_router"]
