"""FastAPI application entry point.

Deliberately thin: it creates the app, wires CORS, mounts the three routers
and exposes a health check. All behaviour lives in app/routers/.

Run with:  uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import DATABASE_URL, create_tables, dispose_engine, engine
from app.routers import collection, expense, user

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger("ganpati")

API_PREFIX = os.getenv("API_PREFIX", "/api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Connecting to %s", DATABASE_URL.rsplit("@", 1)[-1])
    try:
        await create_tables()
        logger.info("Tables ready: TBUSER, TBEXP, TBCOLL")
    except Exception as exc:  # database not reachable yet
        # Not fatal on purpose: /docs and /health stay up so the failure is
        # visible and diagnosable instead of the process dying on boot.
        logger.error("Could not create tables: %s", exc)
    yield
    await dispose_engine()


app = FastAPI(
    title=os.getenv("APP_NAME", "Ganpati Utsav Management API"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description=(
        "Backend for a residential society's Ganpati festival app.\n\n"
        "* **Users** (`TBUSER`) - committee members\n"
        "* **Collections** (`TBCOLL`) - one row per contribution received\n"
        "* **Expenses** (`TBEXP`) - one row per spend\n"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router, prefix=API_PREFIX)
app.include_router(collection.router, prefix=API_PREFIX)
app.include_router(expense.router, prefix=API_PREFIX)


@app.get("/", tags=["Meta"], summary="Service banner")
async def root() -> dict:
    return {
        "name": app.title,
        "version": app.version,
        "docs": "/docs",
        "api_prefix": API_PREFIX,
    }


@app.get("/health", tags=["Meta"], summary="Liveness probe with a real DB round trip")
async def health() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database = "connected"
    except Exception:
        database = "unavailable"
    return {"status": "ok" if database == "connected" else "degraded", "database": database}
