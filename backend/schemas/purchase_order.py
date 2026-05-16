from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

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
    status: PurchaseOrderStatus
    created_at: datetime
    updated_at: datetime
