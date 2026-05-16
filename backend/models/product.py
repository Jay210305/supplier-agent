from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.supplier import Supplier


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "sku", name="uq_products_supplier_sku"),
        CheckConstraint("unit_price >= 0", name="ck_products_unit_price_nonneg"),
        CheckConstraint("lead_time_days >= 0", name="ck_products_lead_time_nonneg"),
        CheckConstraint("available_stock >= 0", name="ck_products_stock_nonneg"),
        CheckConstraint("minimum_order_quantity >= 0", name="ck_products_moq_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(2000))
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    available_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="products")
