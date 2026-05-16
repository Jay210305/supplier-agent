from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from schemas.procurement_request import (
    ProcurementConstraints,
    ProcurementItem,
    ProcurementPriority,
    ProcurementRequestExtracted,
)


class ScoreSuppliersBody(BaseModel):
    """POST /scoring/score_suppliers — WLC ranking for a procurement request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    procurement_request: ProcurementRequestExtracted
    top_n: Annotated[int, Field(default=3, ge=1, le=50)] = 3


class ScoredSupplierOut(BaseModel):
    supplier_id: int
    id: int | None = None
    name: str
    ruc: str
    email: str
    rating: float
    extended_total_pen: float
    bottleneck_lead_days: int
    price_score: float
    delivery_score: float
    reliability_score: float
    wlc_score: float
    lines: list[dict[str, Any]] = Field(default_factory=list)


class ScoreSuppliersResponse(BaseModel):
    procurement_request: ProcurementRequestExtracted
    scored_suppliers: list[ScoredSupplierOut]
    top_suppliers: list[ScoredSupplierOut]
    scoring_fallback_used: bool = False


class JustificationBody(BaseModel):
    """POST /scoring/justification — LLM pick among WLC top suppliers."""

    model_config = ConfigDict(str_strip_whitespace=True)

    procurement_request: ProcurementRequestExtracted
    top_suppliers: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=10)]


class JustificationResponse(BaseModel):
    recommended_supplier_id: int
    justification: str
    runner_up_supplier_id: int | None = None
    llm_fallback_used: bool = False
    request_id: str
    items: list[ProcurementItem]
    constraints: ProcurementConstraints
    priority: ProcurementPriority | None = None

    @field_serializer("constraints", when_used="json")
    def _constraints_json(self, value: ProcurementConstraints) -> dict[str, Any]:
        return value.model_dump(mode="json")
