"""Loads the named SQL statements stored in the `sql/queries/` folder.

Keeping the SQL in .sql files rather than inline strings means it is
syntax-highlighted, reviewable on its own, and can be pasted straight into
psql. Each file is split on `-- name: <identifier>` markers:

    -- name: select_user_by_id
    SELECT ... FROM "TBUSER" WHERE id = :id;

and retrieved with `load("users", "select_user_by_id")`, which returns a
SQLAlchemy `TextClause` ready to execute with bound parameters.

Files are read once and cached, so this costs nothing per request.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from sqlalchemy import TextClause, text

# app/sql_loader.py -> repo root -> sql/queries
QUERY_DIR = Path(__file__).resolve().parent.parent / "sql" / "queries"

_NAME_MARKER = re.compile(r"^--\s*name:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", re.MULTILINE)


@cache
def _parse_file(filename: str) -> dict[str, str]:
    """Split one .sql file into {query_name: sql_text}."""
    path = QUERY_DIR / f"{filename}.sql"
    if not path.is_file():
        raise FileNotFoundError(f"No SQL file at {path}")

    body = path.read_text(encoding="utf-8")
    matches = list(_NAME_MARKER.finditer(body))
    if not matches:
        raise ValueError(f"{path} contains no '-- name:' markers")

    queries: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        statement = body[start:end].strip().rstrip(";").strip()
        if not statement:
            raise ValueError(f"Query '{match.group(1)}' in {path} is empty")
        queries[match.group(1)] = statement
    return queries


@cache
def load(filename: str, query_name: str) -> TextClause:
    """Return one named statement as an executable `TextClause`.

    Raises KeyError with the available names listed, so a typo fails loudly at
    call time rather than producing a confusing database error.
    """
    queries = _parse_file(filename)
    try:
        return text(queries[query_name])
    except KeyError:
        available = ", ".join(sorted(queries))
        raise KeyError(
            f"'{query_name}' is not defined in sql/queries/{filename}.sql. Available: {available}"
        ) from None


def query_names(filename: str) -> list[str]:
    """Every query name defined in a file — used by the test suite."""
    return sorted(_parse_file(filename))
