"""Initial schema: flats, expense_categories, collections, expenses, audit_logs

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-13

The enum columns reuse `app.models.enums.string_enum` so the migration can
never drift from the models: both render VARCHAR(32) plus a CHECK constraint
rather than a native PostgreSQL ENUM type (adding a new payment method later
is then an ordinary migration instead of an ALTER TYPE).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import JSONType, MoneyType
from app.models.enums import (
    AuditAction,
    AuditEntity,
    CollectionStatus,
    PaymentMethod,
    string_enum,
)

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------- flats ---
    op.create_table(
        "flats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wing", sa.String(length=4), nullable=False),
        sa.Column("flat_number", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=32), nullable=False),
        sa.Column("owner_name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_flats"),
        sa.UniqueConstraint("flat_number", name="uq_flats_flat_number"),
        sa.UniqueConstraint("wing", "display_name", name="uq_flats_wing_display_name"),
    )
    op.create_index("ix_flats_wing", "flats", ["wing"])
    op.create_index("ix_flats_is_active", "flats", ["is_active"])

    # -------------------------------------------------- expense_categories ---
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expense_categories"),
        sa.UniqueConstraint("code", name="uq_expense_categories_code"),
        sa.UniqueConstraint("name", name="uq_expense_categories_name"),
    )

    # ------------------------------------------------------- collections ---
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("flat_id", sa.Integer(), nullable=False),
        sa.Column("amount", MoneyType, nullable=False),
        sa.Column("payment_method", string_enum(PaymentMethod, "payment_method"), nullable=False),
        sa.Column(
            "status",
            string_enum(CollectionStatus, "collection_status"),
            server_default=CollectionStatus.CONFIRMED.value,
            nullable=False,
        ),
        sa.Column("reference_no", sa.String(length=64), nullable=True),
        sa.Column("collected_on", sa.Date(), nullable=False),
        sa.Column("collected_by", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="ck_collections_amount_positive"),
        sa.ForeignKeyConstraint(
            ["flat_id"], ["flats.id"], name="fk_collections_flat_id_flats", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collections"),
    )
    op.create_index("ix_collections_flat_id", "collections", ["flat_id"])
    op.create_index("ix_collections_collected_on", "collections", ["collected_on"])
    op.create_index("ix_collections_payment_method", "collections", ["payment_method"])
    op.create_index("ix_collections_status", "collections", ["status"])

    # ---------------------------------------------------------- expenses ---
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", MoneyType, nullable=False),
        sa.Column("payment_method", string_enum(PaymentMethod, "payment_method"), nullable=False),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("vendor", sa.String(length=160), nullable=True),
        sa.Column("reference_no", sa.String(length=64), nullable=True),
        sa.Column("paid_by", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["expense_categories.id"],
            name="fk_expenses_category_id_expense_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
    )
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])
    op.create_index("ix_expenses_spent_on", "expenses", ["spent_on"])
    op.create_index("ix_expenses_payment_method", "expenses", ["payment_method"])
    op.create_index("ix_expenses_title", "expenses", ["title"])

    # -------------------------------------------------------- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", string_enum(AuditEntity, "audit_entity"), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", string_enum(AuditAction, "audit_action"), nullable=False),
        sa.Column("changes", JSONType, nullable=True),
        sa.Column("snapshot", JSONType, nullable=True),
        sa.Column("actor", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index(
        "ix_audit_logs_entity_type_entity_id", "audit_logs", ["entity_type", "entity_id"]
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type_entity_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_expenses_title", table_name="expenses")
    op.drop_index("ix_expenses_payment_method", table_name="expenses")
    op.drop_index("ix_expenses_spent_on", table_name="expenses")
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_table("expenses")

    op.drop_index("ix_collections_status", table_name="collections")
    op.drop_index("ix_collections_payment_method", table_name="collections")
    op.drop_index("ix_collections_collected_on", table_name="collections")
    op.drop_index("ix_collections_flat_id", table_name="collections")
    op.drop_table("collections")

    op.drop_table("expense_categories")

    op.drop_index("ix_flats_is_active", table_name="flats")
    op.drop_index("ix_flats_wing", table_name="flats")
    op.drop_table("flats")
