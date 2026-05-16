from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.enums import CatalogSourceKind


class CatalogSourceBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    name: Annotated[str, Field(min_length=1, max_length=120)]
    kind: CatalogSourceKind
    adapter_key: Annotated[str, Field(min_length=1, max_length=64)]
    endpoint: Annotated[str, Field(min_length=1, max_length=512)]
    is_enabled: bool = True
    country: Annotated[str | None, Field(default=None, min_length=2, max_length=2)] = None
    currency: Annotated[str, Field(default="PEN", min_length=3, max_length=3)] = "PEN"
    reliability_rating: Annotated[
        Decimal, Field(ge=0, le=10, max_digits=4, decimal_places=2)
    ] = Decimal("5.00")
    rate_limit_per_min: Annotated[int, Field(ge=1, le=1000)] = 20
    timeout_seconds: Annotated[int, Field(ge=1, le=120)] = 15
    auth: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    notes: Annotated[str | None, Field(default=None, max_length=2000)] = None

    @field_validator("country")
    @classmethod
    def upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


class CatalogSourceCreate(CatalogSourceBase):
    pass


class CatalogSourceUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=120)] = None
    kind: CatalogSourceKind | None = None
    adapter_key: Annotated[str | None, Field(default=None, min_length=1, max_length=64)] = None
    endpoint: Annotated[str | None, Field(default=None, min_length=1, max_length=512)] = None
    is_enabled: bool | None = None
    country: Annotated[str | None, Field(default=None, min_length=2, max_length=2)] = None
    currency: Annotated[str | None, Field(default=None, min_length=3, max_length=3)] = None
    reliability_rating: Annotated[
        Decimal | None, Field(default=None, ge=0, le=10, max_digits=4, decimal_places=2)
    ] = None
    rate_limit_per_min: Annotated[int | None, Field(default=None, ge=1, le=1000)] = None
    timeout_seconds: Annotated[int | None, Field(default=None, ge=1, le=120)] = None
    auth: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    notes: Annotated[str | None, Field(default=None, max_length=2000)] = None


class CatalogSourceRead(CatalogSourceBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AdapterInfo(BaseModel):
    key: str
    kind: CatalogSourceKind
    description: str
    requires_auth: bool
    auth_fields: list[str] = Field(default_factory=list)
    config_fields: list[str] = Field(default_factory=list)


class ExternalProductResult(BaseModel):
    """Normalized product hit from any external catalog source."""

    model_config = ConfigDict(str_strip_whitespace=True)

    source_id: int
    source_name: str
    adapter_key: str
    product_name: Annotated[str, Field(min_length=1, max_length=512)]
    description: Annotated[str | None, Field(default=None, max_length=4000)] = None
    sku: Annotated[str | None, Field(default=None, max_length=128)] = None
    url: Annotated[str | None, Field(default=None, max_length=2048)] = None
    image_url: Annotated[str | None, Field(default=None, max_length=2048)] = None
    unit_price: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
    currency: Annotated[str, Field(default="PEN", min_length=3, max_length=3)] = "PEN"
    lead_time_days: Annotated[int, Field(ge=0, le=3650)] = 7
    available_stock: Annotated[int, Field(ge=0)] = 9999
    minimum_order_quantity: Annotated[int, Field(ge=1)] = 1
    rating: Annotated[Decimal, Field(ge=0, le=10, max_digits=4, decimal_places=2)] = Decimal(
        "5.00"
    )
    raw: dict[str, Any] | None = None


class TestSourceBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: Annotated[str, Field(min_length=1, max_length=255)] = "laptop"
    limit: Annotated[int, Field(ge=1, le=25)] = 5


class TestSourceResponse(BaseModel):
    source_id: int
    source_name: str
    adapter_key: str
    query: str
    elapsed_ms: int
    ok: bool
    error: str | None = None
    results: list[ExternalProductResult] = Field(default_factory=list)


class ExternalSearchBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: Annotated[str, Field(min_length=1, max_length=255)]
    limit: Annotated[int, Field(ge=1, le=50)] = 10
    source_ids: list[int] | None = None


class ExternalSearchResponse(BaseModel):
    query: str
    sources_used: list[str]
    elapsed_ms: int
    results: list[ExternalProductResult]
