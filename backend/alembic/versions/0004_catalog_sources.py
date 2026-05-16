"""phase 4 — catalog_sources + catalog_search_cache

Revision ID: 0004_catalog_sources
Revises: 0003_po_request_payload
Create Date: 2026-05-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_catalog_sources"
down_revision: str | None = "0003_po_request_payload"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("adapter_key", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=False),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="PEN",
        ),
        sa.Column(
            "reliability_rating",
            sa.Numeric(precision=4, scale=2),
            nullable=False,
            server_default="5.00",
        ),
        sa.Column(
            "rate_limit_per_min",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
        sa.Column(
            "timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
        sa.Column("auth", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
            "kind IN ('website','email')", name="ck_catalog_sources_kind_allowed"
        ),
        sa.CheckConstraint(
            "rate_limit_per_min > 0", name="ck_catalog_sources_rate_limit_pos"
        ),
        sa.CheckConstraint(
            "timeout_seconds > 0", name="ck_catalog_sources_timeout_pos"
        ),
        sa.CheckConstraint(
            "reliability_rating >= 0 AND reliability_rating <= 10",
            name="ck_catalog_sources_rating_range",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_catalog_sources_name"), "catalog_sources", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_catalog_sources_kind"), "catalog_sources", ["kind"], unique=False
    )
    op.create_index(
        op.f("ix_catalog_sources_adapter_key"),
        "catalog_sources",
        ["adapter_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_catalog_sources_is_enabled"),
        "catalog_sources",
        ["is_enabled"],
        unique=False,
    )

    op.create_table(
        "catalog_search_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("query_text", sa.String(length=512), nullable=False),
        sa.Column(
            "results", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["catalog_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "query_hash", name="uq_catalog_cache_source_query"
        ),
    )
    op.create_index(
        op.f("ix_catalog_search_cache_source_id"),
        "catalog_search_cache",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_catalog_search_cache_query_hash"),
        "catalog_search_cache",
        ["query_hash"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_cache_expires_at",
        "catalog_search_cache",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_cache_expires_at", table_name="catalog_search_cache")
    op.drop_index(
        op.f("ix_catalog_search_cache_query_hash"), table_name="catalog_search_cache"
    )
    op.drop_index(
        op.f("ix_catalog_search_cache_source_id"), table_name="catalog_search_cache"
    )
    op.drop_table("catalog_search_cache")

    op.drop_index(op.f("ix_catalog_sources_is_enabled"), table_name="catalog_sources")
    op.drop_index(op.f("ix_catalog_sources_adapter_key"), table_name="catalog_sources")
    op.drop_index(op.f("ix_catalog_sources_kind"), table_name="catalog_sources")
    op.drop_index(op.f("ix_catalog_sources_name"), table_name="catalog_sources")
    op.drop_table("catalog_sources")
