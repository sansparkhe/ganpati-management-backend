"""Application configuration.

Everything that could change between machines/environments lives here and is
read from environment variables (or a local `.env` file). No credentials are
ever hard-coded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class WingConfig:
    """A single wing of the society, e.g. wing "A" with 12 flats."""

    code: str
    flat_count: int


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------------------------------------------------------- app ---
    APP_NAME: str = "Ganpati Utsav Management API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api"

    # ----------------------------------------------------------- database ---
    # Example: postgresql+psycopg://ganpati:secret@localhost:5432/ganpati_db
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ganpati_db"
    # Optional separate database used by the pytest suite.
    TEST_DATABASE_URL: str | None = None
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # --------------------------------------------------------------- cors ---
    # Comma separated list. For Flutter web dev this is typically
    # "http://localhost:3000,http://localhost:8080". Android emulators and
    # real devices do not send an Origin header, so they are unaffected.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://127.0.0.1:8080"
    CORS_ALLOW_CREDENTIALS: bool = False

    # ------------------------------------------------------------- society ---
    # "<WING>:<number of flats>" pairs, comma separated.
    #
    #   IMPORTANT / KNOWN DISCREPANCY
    #   -----------------------------
    #   A:12,B:12 == 24 flats, but the original requirement mentions 28 flats.
    #   Nothing in this codebase assumes either number: the flats are generated
    #   from this variable. Set EXPECTED_TOTAL_FLATS to the number you believe
    #   is correct and the API will report the mismatch at
    #   GET /api/flats/config until the two agree.
    #
    #   To add the missing 4 flats, use ONE of:
    #     SOCIETY_WINGS=A:14,B:14        -> A1..A14, B1..B14  (28)
    #     SOCIETY_WINGS=A:12,B:12,C:4    -> adds a C wing     (28)
    #   then re-run `python -m scripts.seed` (it is idempotent).
    SOCIETY_WINGS: str = "A:12,B:12"
    EXPECTED_TOTAL_FLATS: int = 28

    # ---------------------------------------------------------- behaviour ---
    ALLOW_FUTURE_DATES: bool = False
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    RECENT_ITEMS_LIMIT: int = Field(default=5, ge=1, le=50)
    CURRENCY_CODE: str = "INR"
    CURRENCY_SYMBOL: str = "₹"

    # ------------------------------------------------------------ helpers ---
    @field_validator("SOCIETY_WINGS")
    @classmethod
    def _validate_wings(cls, value: str) -> str:
        if not parse_wings(value):
            raise ValueError('SOCIETY_WINGS must look like "A:12,B:12" (wing code : flat count)')
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def wings(self) -> list[WingConfig]:
        return parse_wings(self.SOCIETY_WINGS)

    @property
    def wing_codes(self) -> list[str]:
        return [wing.code for wing in self.wings]

    @property
    def configured_flat_count(self) -> int:
        return sum(wing.flat_count for wing in self.wings)

    @property
    def flat_count_matches_expectation(self) -> bool:
        return self.configured_flat_count == self.EXPECTED_TOTAL_FLATS

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def async_database_url(self) -> str:
        """DSN for the application's async engine."""
        return _normalise_async_url(self.TEST_DATABASE_URL or self.DATABASE_URL)

    @property
    def sync_database_url(self) -> str:
        """DSN for Alembic, which runs synchronously."""
        return _normalise_sync_url(self.DATABASE_URL)


_WING_PATTERN = re.compile(r"^([A-Za-z0-9]{1,4}):(\d{1,3})$")


def parse_wings(raw: str) -> list[WingConfig]:
    """Parse `"A:12,B:12"` into wing configuration objects."""
    wings: list[WingConfig] = []
    seen: set[str] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = _WING_PATTERN.match(chunk)
        if not match:
            return []
        code = match.group(1).upper()
        count = int(match.group(2))
        if count <= 0 or code in seen:
            return []
        seen.add(code)
        wings.append(WingConfig(code=code, flat_count=count))
    return wings


def _normalise_async_url(url: str) -> str:
    """Make sure the URL carries an async-capable driver."""
    if url.startswith("postgresql+psycopg://") or url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):  # Heroku-style
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _normalise_sync_url(url: str) -> str:
    """psycopg3 is both sync and async, so only the async-only drivers differ."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url.replace("+aiosqlite", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
