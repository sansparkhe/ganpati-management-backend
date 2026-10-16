"""Central configuration: the only module that reads secrets.

Values come from real environment variables first, then from
private/.env (git-ignored). Override the file location with ENV_FILE.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# app/config.py -> repo root is two levels up
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = Path(os.getenv("ENV_FILE", BASE_DIR / "app" /"private" / ".env"))

# Real environment variables take precedence over values in .env
load_dotenv(ENV_FILE)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required setting {name}. "
            f"Check your private/.env file at {ENV_FILE}."
        )
    return value


def _load_crypto_key() -> bytes:
    raw = os.getenv("CRYPTO_KEY")

    if not raw:
        raise RuntimeError("Missing required setting CRYPTO_KEY.")

    key = raw.encode("utf-8")

    return key

# --- Secrets (required) ------------------------------------------------------
DATABASE_URL: str = _require("DATABASE_URL")
CRYPTO_KEY: bytes = _load_crypto_key()
LEDGER_PASSPHRASE: str = _require("LEDGER_PASSPHRASE")


# --- App settings (optional, have defaults) ---------------------------------
APP_NAME: str = os.getenv("APP_NAME", "Ganpati Utsav Management API")
APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
API_PREFIX: str = os.getenv("API_PREFIX", "/api")

CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]