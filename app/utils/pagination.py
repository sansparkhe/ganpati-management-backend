"""Pagination primitives shared by every list endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class PaginationParams:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def page_count(total: int, limit: int) -> int:
    if limit <= 0:
        return 0
    return ceil(total / limit) if total else 0
