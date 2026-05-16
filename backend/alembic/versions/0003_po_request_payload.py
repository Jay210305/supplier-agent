"""purchase_orders: request_id + payload JSONB

Revision ID: 0003_po_request_payload
Revises: 0002_phase2
Create Date: 2026-05-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_po_request_payload"
down_revision: str | None = "0002_phase2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        op.f("ix_purchase_orders_request_id"),
        "purchase_orders",
        ["request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_orders_request_id"), table_name="purchase_orders")
    op.drop_column("purchase_orders", "payload")
    op.drop_column("purchase_orders", "request_id")
