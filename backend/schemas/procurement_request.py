from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class ProcurementPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProcurementItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    product: Annotated[str, Field(min_length=1, max_length=255)]
    quantity: Annotated[int, Field(ge=1, le=1_000_000)]


class ProcurementConstraints(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    max_budget: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
    currency: Annotated[str, Field(default="PEN", max_length=3)] = "PEN"
    delivery_before: date | None = None

    @field_serializer("max_budget", when_used="json")
    def budget_to_number(self, value: Decimal) -> float:
        return float(value)


class ProcurementRequestExtracted(BaseModel):
    """Validated shape for LLM entity extraction output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: Annotated[str, Field(min_length=1, max_length=64)]
    items: Annotated[list[ProcurementItem], Field(min_length=1)]
    constraints: ProcurementConstraints
    priority: ProcurementPriority | None = None

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class ProcurementParseBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email_body: Annotated[str, Field(min_length=1, max_length=100_000)]
    include_external: bool = True
    source_ids: list[int] | None = None


class ProcurementJustificationLLM(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recommended_supplier_id: int
    justification: Annotated[str, Field(min_length=1, max_length=8000)]
    runner_up_supplier_id: int | None = None


class ProcurementParseResponse(ProcurementRequestExtracted):
    """LLM extraction plus catalog-based budget lower bound (n8n uses budget_exceeded)."""

    budget_exceeded: bool = False
    estimated_minimum_total: Decimal | None = None
    sources_used: list[str] = []
    external_candidate_count: int = 0

    @field_serializer("estimated_minimum_total", when_used="json")
    def _ser_est(self, value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value)
