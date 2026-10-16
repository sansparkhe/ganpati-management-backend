# scripts/generate_schema.py
"""
Regenerate schema.sql from app/models/ — for MySQL.

Run with:  python -m scripts.generate_schema
"""
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mysql

# Import your Base and make sure all models are registered on it.
# Adjust this import to match your actual models module.
from app.database import Base
from app import models   # noqa: F401  (side-effect import: registers all model classes)

MYSQL_DIALECT = mysql.dialect()

HEADER = """\
-- Schema for the Ganpati Utsav backend (MySQL).
--
-- Generated from app/models/. Do not edit by hand — regenerate instead.
-- Run: python -m scripts.generate_schema
"""

def generate():
    lines = [HEADER]
    for table in Base.metadata.sorted_tables:
        create_stmt = str(CreateTable(table).compile(dialect=MYSQL_DIALECT)).strip()
        lines.append(create_stmt + ";\n")
        for index in table.indexes:
            idx_stmt = str(CreateIndex(index).compile(dialect=MYSQL_DIALECT)).strip()
            lines.append(idx_stmt + ";")
        lines.append("")  # blank line between tables
    return "\n".join(lines)

if __name__ == "__main__":
    sql = generate()
    with open("schema.sql", "w") as f:
        f.write(sql)
    print("Wrote schema.sql")