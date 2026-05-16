from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.product import Product
    from models.purchase_order import PurchaseOrder


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(r"ruc ~ '^\d{11}$'", name="ck_suppliers_ruc_eleven_digits"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ruc: Mapped[str] = mapped_column(String(11), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(512))
    rating: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("5.00"))
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

    products: Mapped[list[Product]] = relationship(
        "Product", back_populates="supplier", cascade="all, delete-orphan"
    )
    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        "PurchaseOrder", back_populates="supplier"
    )
