from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _ruc_digits(v: str) -> str:
    if not v.isdigit() or len(v) != 11:
        raise ValueError("RUC must be exactly 11 digits")
    return v


class SupplierBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_name: Annotated[str, Field(min_length=1, max_length=255)]
    ruc: Annotated[str, Field(min_length=11, max_length=11)]
    email: EmailStr
    phone: Annotated[str | None, Field(default=None, max_length=20)] = None
    address: Annotated[str | None, Field(default=None, max_length=512)] = None
    rating: Annotated[Decimal, Field(ge=0, le=10, max_digits=4, decimal_places=2)] = Decimal(
        "5.00"
    )
    is_active: bool = True

    @field_validator("ruc")
    @classmethod
    def validate_ruc(cls, v: str) -> str:
        return _ruc_digits(v)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_name: Annotated[str | None, Field(default=None, min_length=1, max_length=255)] = None
    ruc: Annotated[str | None, Field(default=None, min_length=11, max_length=11)] = None
    email: EmailStr | None = None
    phone: Annotated[str | None, Field(default=None, max_length=20)] = None
    address: Annotated[str | None, Field(default=None, max_length=512)] = None
    rating: Annotated[
        Decimal | None, Field(default=None, ge=0, le=10, max_digits=4, decimal_places=2)
    ] = None
    is_active: bool | None = None

    @field_validator("ruc")
    @classmethod
    def validate_ruc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _ruc_digits(v)


class SupplierRead(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
