from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class CatalogSearchCache(Base):
    __tablename__ = "catalog_search_cache"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "query_hash", name="uq_catalog_cache_source_query"
        ),
        Index("ix_catalog_cache_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(String(512), nullable=False)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
