"""phase 2 — suppliers, products, purchase_orders, procurement_logs

Revision ID: 0002_phase2
Revises: 0001_phase1
Create Date: 2026-05-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase2"
down_revision: str | None = "0001_phase1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("ruc", sa.String(length=11), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column(
            "rating",
            sa.Numeric(precision=4, scale=2),
            nullable=False,
            server_default="5.00",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(r"ruc ~ '^\d{11}$'", name="ck_suppliers_ruc_eleven_digits"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ruc"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_suppliers_company_name"), "suppliers", ["company_name"], unique=False)
    op.create_index(op.f("ix_suppliers_is_active"), "suppliers", ["is_active"], unique=False)
    op.create_index(op.f("ix_suppliers_ruc"), "suppliers", ["ruc"], unique=False)
    op.create_index(op.f("ix_suppliers_email"), "suppliers", ["email"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="PEN",
        ),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column(
            "available_stock",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "minimum_order_quantity",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_products_unit_price_nonneg"),
        sa.CheckConstraint("lead_time_days >= 0", name="ck_products_lead_time_nonneg"),
        sa.CheckConstraint("available_stock >= 0", name="ck_products_stock_nonneg"),
        sa.CheckConstraint("minimum_order_quantity >= 0", name="ck_products_moq_nonneg"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_id", "sku", name="uq_products_supplier_sku"),
    )
    op.create_index(op.f("ix_products_is_active"), "products", ["is_active"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)
    op.create_index(op.f("ix_products_supplier_id"), "products", ["supplier_id"], unique=False)

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="PEN",
        ),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("pdf_path", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','SENT')",
            name="ck_purchase_orders_status_allowed",
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_purchase_orders_status"), "purchase_orders", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_purchase_orders_supplier_id"), "purchase_orders", ["supplier_id"], unique=False
    )

    op.create_table(
        "procurement_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_source", sa.String(length=128), nullable=True),
        sa.Column("message", sa.String(length=2000), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default="INFO",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('DEBUG','INFO','WARNING','ERROR')",
            name="ck_procurement_logs_severity_allowed",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_procurement_logs_created_at"), "procurement_logs", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_procurement_logs_event_source"),
        "procurement_logs",
        ["event_source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_procurement_logs_event_type"), "procurement_logs", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_procurement_logs_severity"), "procurement_logs", ["severity"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_procurement_logs_severity"), table_name="procurement_logs")
    op.drop_index(op.f("ix_procurement_logs_event_type"), table_name="procurement_logs")
    op.drop_index(op.f("ix_procurement_logs_event_source"), table_name="procurement_logs")
    op.drop_index(op.f("ix_procurement_logs_created_at"), table_name="procurement_logs")
    op.drop_table("procurement_logs")

    op.drop_index(op.f("ix_purchase_orders_supplier_id"), table_name="purchase_orders")
    op.drop_index(op.f("ix_purchase_orders_status"), table_name="purchase_orders")
    op.drop_table("purchase_orders")

    op.drop_index(op.f("ix_products_supplier_id"), table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_is_active"), table_name="products")
    op.drop_table("products")

    op.drop_index(op.f("ix_suppliers_email"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_ruc"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_is_active"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_company_name"), table_name="suppliers")
    op.drop_table("suppliers")
