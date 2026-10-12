import re
from pathlib import Path
from app.config import DATABASE_URL

from sqlalchemy import inspect

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


_CREATE_TABLE_RE = re.compile(
    r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"?([A-Za-z_]\w*)"?',
    re.IGNORECASE,
)

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DB_URL = DATABASE_URL

engine = create_async_engine(
    DB_URL,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session



def _strip_comments(sql: str) -> str:
    """Remove `-- ...` line comments so they don't end up inside statements."""
    return re.sub(r"--[^\n]*", "", sql)


async def create_tables() -> None:
    raw_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    sql = _strip_comments(raw_sql)

    # Tables that schema.sql is expected to create
    expected = {name.lower() for name in _CREATE_TABLE_RE.findall(sql)}

    async with engine.begin() as conn:
        # a. Check which tables already exist
        existing = await conn.run_sync(
            lambda sync_conn: {t.lower() for t in inspect(sync_conn).get_table_names()}
        )

        missing = expected - existing
        if not missing:
            print("All tables exist, skipping schema.sql")
            return

        # b. At least one table is missing: run the entire schema.sql
        print(f"Missing tables: {sorted(missing)}. Running schema.sql")

        for stmt in (s.strip() for s in sql.split(";")):
            if stmt:
                await conn.exec_driver_sql(stmt)

        print("schema.sql executed")


async def dispose_engine():
    await engine.dispose()