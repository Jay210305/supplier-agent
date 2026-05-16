from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_id: int = Field(ge=1)
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str | None, Field(default=None, max_length=2000)] = None
    sku: Annotated[str, Field(min_length=1, max_length=64)]
    unit_price: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
    currency: Annotated[str, Field(default="PEN", max_length=3)] = "PEN"
    lead_time_days: Annotated[int, Field(ge=0, le=3650)]
    available_stock: Annotated[int, Field(ge=0)] = 0
    minimum_order_quantity: Annotated[int, Field(ge=0)] = 1
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=255)] = None
    description: Annotated[str | None, Field(default=None, max_length=2000)] = None
    sku: Annotated[str | None, Field(default=None, min_length=1, max_length=64)] = None
    unit_price: Annotated[Decimal | None, Field(default=None, ge=0, decimal_places=2)] = None
    currency: Annotated[str | None, Field(default=None, max_length=3)] = None
    lead_time_days: Annotated[int | None, Field(default=None, ge=0, le=3650)] = None
    available_stock: Annotated[int | None, Field(default=None, ge=0)] = None
    minimum_order_quantity: Annotated[int | None, Field(default=None, ge=0)] = None
    is_active: bool | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
