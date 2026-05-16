from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.enums import PurchaseOrderStatus

if TYPE_CHECKING:
    from models.supplier import Supplier


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(
            PurchaseOrderStatus,
            name="purchase_order_status",
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=PurchaseOrderStatus.PENDING,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    pdf_path: Mapped[str | None] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(String(4000))
    created_by: Mapped[str | None] = mapped_column(String(255))
    approved_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="purchase_orders")
