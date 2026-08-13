"""Importing this package registers every model on `Base.metadata`.

Alembic's env.py relies on that, so keep all models exported here.
"""

from app.models.audit import AuditLog
from app.models.base import Base, JSONType, MoneyType, TimestampMixin
from app.models.category import ExpenseCategory
from app.models.collection import Collection
from app.models.enums import (
    AuditAction,
    AuditEntity,
    CollectionStatus,
    PaymentMethod,
)
from app.models.expense import Expense
from app.models.flat import Flat

__all__ = [
    "AuditAction",
    "AuditEntity",
    "AuditLog",
    "Base",
    "Collection",
    "CollectionStatus",
    "Expense",
    "ExpenseCategory",
    "Flat",
    "JSONType",
    "MoneyType",
    "PaymentMethod",
    "TimestampMixin",
]
