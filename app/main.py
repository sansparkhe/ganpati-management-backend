"""FastAPI application factory.

Deliberately thin: configuration, middleware, error handlers and router
mounting only. All behaviour lives in routers/ and services/.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import dispose_engine
from app.core.error_handlers import register_error_handlers
from app.routers import api_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("ganpati")

DESCRIPTION = f"""
Backend for a residential society's **Ganpati festival** management app.

* **Collections** - one row per contribution, editable and fully audited
* **Expenses** - one row per spend, categorised
* **Finance** - `remaining_balance` is always calculated, never stored
* **Dashboard** - one call powers the whole home screen

All responses share the same envelope:

```json
{{ "success": true, "data": {{ }}, "message": "..." }}
```

Errors use the same shape with `"success": false` plus a machine readable
`error` code such as `FLAT_NOT_FOUND`.

Money is stored as `NUMERIC(12,2)` and computed with `Decimal` - never a float.
Amounts are sent over JSON as plain numbers ({settings.CURRENCY_SYMBOL}2500.00 -> `2500.0`).
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.APP_ENV)
    logger.info(
        "Society configuration: %s -> %d flats",
        settings.SOCIETY_WINGS,
        settings.configured_flat_count,
    )
    if not settings.flat_count_matches_expectation:
        logger.warning(
            "FLAT COUNT DISCREPANCY: SOCIETY_WINGS produces %d flats but "
            "EXPECTED_TOTAL_FLATS is %d. Nothing has been assumed - see "
            "GET %s/flats/config for how to fix it.",
            settings.configured_flat_count,
            settings.EXPECTED_TOTAL_FLATS,
            settings.API_PREFIX,
        )
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={"name": "Ganpati Utsav Committee"},
    )

    # CORS: origins come from the environment. Flutter mobile builds do not send
    # an Origin header, so this only matters for Flutter Web / browser testing.
    origins = settings.cors_origin_list
    if settings.is_production and "*" in origins:
        raise RuntimeError("CORS_ORIGINS must not be '*' in production")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count"],
    )

    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.API_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "success": True,
            "data": {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "docs": "/docs",
                "api_prefix": settings.API_PREFIX,
            },
            "message": "Ganpati Utsav backend is running",
        }

    return app


app = create_app()
