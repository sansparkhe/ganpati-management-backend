"""Application level errors.

Every error carries a machine readable `error_code` so the Flutter app can
branch on it without parsing English messages.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all expected (non-bug) errors."""

    status_code: int = 400
    error_code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(AppError):
    """The request is valid but conflicts with existing data (HTTP 409)."""

    status_code = 409
    error_code = "CONFLICT"


class BadRequestError(AppError):
    status_code = 400
    error_code = "BAD_REQUEST"


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# Concrete, domain specific errors. Keeping them here means the same message
# and code are produced no matter which service raises them.
# --------------------------------------------------------------------------
class FlatNotFoundError(NotFoundError):
    error_code = "FLAT_NOT_FOUND"

    def __init__(self, *, flat_id: int | None = None, flat_number: str | None = None) -> None:
        if flat_number:
            message = f"Flat {flat_number} does not exist"
        else:
            message = f"Flat with id {flat_id} does not exist"
        super().__init__(message)


class CollectionNotFoundError(NotFoundError):
    error_code = "COLLECTION_NOT_FOUND"

    def __init__(self, collection_id: int) -> None:
        super().__init__(f"Collection with id {collection_id} does not exist")


class ExpenseNotFoundError(NotFoundError):
    error_code = "EXPENSE_NOT_FOUND"

    def __init__(self, expense_id: int) -> None:
        super().__init__(f"Expense with id {expense_id} does not exist")


class CategoryNotFoundError(NotFoundError):
    error_code = "CATEGORY_NOT_FOUND"

    def __init__(self, *, category_id: int | None = None, code: str | None = None) -> None:
        if code:
            message = f"Expense category '{code}' does not exist"
        else:
            message = f"Expense category with id {category_id} does not exist"
        super().__init__(message)


class DuplicateFlatError(ConflictError):
    error_code = "DUPLICATE_FLAT"

    def __init__(self, flat_number: str) -> None:
        super().__init__(f"Flat {flat_number} already exists")


class DuplicateCategoryError(ConflictError):
    error_code = "DUPLICATE_CATEGORY"

    def __init__(self, code: str) -> None:
        super().__init__(f"Expense category '{code}' already exists")


class InvalidWingError(BadRequestError):
    error_code = "INVALID_WING"

    def __init__(self, wing: str, allowed: list[str]) -> None:
        super().__init__(
            f"Wing '{wing}' is not valid. Allowed wings: {', '.join(allowed) or 'none configured'}",
            details={"allowed_wings": allowed},
        )


class FlatHasCollectionsError(ConflictError):
    error_code = "FLAT_HAS_COLLECTIONS"

    def __init__(self, flat_number: str, count: int) -> None:
        super().__init__(
            f"Flat {flat_number} has {count} collection(s) recorded and cannot be deleted. "
            "Deactivate it instead (PATCH /api/flats/{id} with is_active=false).",
            details={"collection_count": count},
        )


class CategoryInUseError(ConflictError):
    error_code = "CATEGORY_IN_USE"

    def __init__(self, code: str, count: int) -> None:
        super().__init__(
            f"Expense category '{code}' is used by {count} expense(s) and cannot be deleted. "
            "Deactivate it instead.",
            details={"expense_count": count},
        )
