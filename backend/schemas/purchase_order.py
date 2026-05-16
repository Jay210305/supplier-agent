from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from models.enums import PurchaseOrderStatus


class PurchaseOrderBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_id: int = Field(ge=1)
    currency: Annotated[str, Field(default="PEN", max_length=3)] = "PEN"
    total_amount: Annotated[
        Decimal | None, Field(default=None, ge=0, max_digits=12, decimal_places=2)
    ] = None
    pdf_path: Annotated[str | None, Field(default=None, max_length=512)] = None
    notes: Annotated[str | None, Field(default=None, max_length=4000)] = None
    created_by: Annotated[str | None, Field(default=None, max_length=255)] = None
    approved_by: Annotated[str | None, Field(default=None, max_length=255)] = None


class PurchaseOrderCreate(PurchaseOrderBase):
    status: PurchaseOrderStatus = PurchaseOrderStatus.PENDING


class PurchaseOrderUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: PurchaseOrderStatus | None = None
    currency: Annotated[str | None, Field(default=None, max_length=3)] = None
    total_amount: Annotated[
        Decimal | None, Field(default=None, ge=0, max_digits=12, decimal_places=2)
    ] = None
    pdf_path: Annotated[str | None, Field(default=None, max_length=512)] = None
    notes: Annotated[str | None, Field(default=None, max_length=4000)] = None
    approved_by: Annotated[str | None, Field(default=None, max_length=255)] = None


class PurchaseOrderRead(PurchaseOrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: str | None = None
    payload: dict[str, Any] | None = None
    status: PurchaseOrderStatus
    created_at: datetime
    updated_at: datetime


class OrderGenerateResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    purchase_order_id: int
    request_id: Annotated[str, Field(min_length=1, max_length=64)]
    supplier_id: int
    supplier_name: str
    pdf_path: str | None = None
    total_amount_pen: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
    justification: str
    runner_up_supplier_id: int | None = None
    scoring_snapshot: list[dict[str, Any]] = Field(default_factory=list)

    @field_serializer("total_amount_pen", when_used="json")
    def _ser_total(self, value: Decimal) -> float:
        return float(value)
