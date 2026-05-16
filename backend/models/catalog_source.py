from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.enums import CatalogSourceKind


class CatalogSource(Base):
    __tablename__ = "catalog_sources"
    __table_args__ = (
        CheckConstraint(
            "rate_limit_per_min > 0", name="ck_catalog_sources_rate_limit_pos"
        ),
        CheckConstraint(
            "timeout_seconds > 0", name="ck_catalog_sources_timeout_pos"
        ),
        CheckConstraint(
            "reliability_rating >= 0 AND reliability_rating <= 10",
            name="ck_catalog_sources_rating_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    kind: Mapped[CatalogSourceKind] = mapped_column(
        Enum(
            CatalogSourceKind,
            name="catalog_source_kind",
            native_enum=False,
            length=16,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    country: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    reliability_rating: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("5.00")
    )
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    auth: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
