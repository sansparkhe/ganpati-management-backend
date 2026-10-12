from __future__ import annotations
import re
from pathlib import Path
from sqlalchemy import text

QUERY_DIR = Path(__file__).resolve().parent.parent / "sql" / "queries"
_NAME_MARKER = re.compile(r"^--\s*name:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", re.MULTILINE)


def _parse_file(filename):
    path = QUERY_DIR / f"{filename}.sql"
    if not path.is_file():
        raise FileNotFoundError(f"No SQL file at {path}")

    body = path.read_text(encoding="utf-8")
    matches = list(_NAME_MARKER.finditer(body))
    if not matches:
        raise ValueError(f"{path} contains no '-- name:' markers")

    queries = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        statement = body[start:end].strip().rstrip(";").strip()
        if not statement:
            raise ValueError(f"Query '{match.group(1)}' in {path} is empty")
        queries[match.group(1)] = statement
    return queries


def load(filename, query_name):
    queries = _parse_file(filename)
    try:
        return text(queries[query_name])
    except KeyError:
        available = ", ".join(sorted(queries))
        raise KeyError(
            f"'{query_name}' is not defined in sql/queries/{filename}.sql. Available: {available}"
        ) from None


def query_names(filename):
    return sorted(_parse_file(filename))
