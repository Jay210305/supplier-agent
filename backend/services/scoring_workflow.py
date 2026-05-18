"""Scoring + justification orchestration for Phase 6 API and n8n workflow."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.supplier import Supplier
from schemas.procurement_request import ProcurementJustificationLLM, ProcurementRequestExtracted
from schemas.scoring import ScoredSupplierOut
from services.ollama_client import OllamaClient, OllamaClientError, OllamaValidationError
from services.candidate_aggregator import aggregate_supplier_quotes
from services.scoring import score_supplier_quotes, top_suppliers

logger = logging.getLogger(__name__)


class ScoringNoSuppliersError(Exception):
    """No eligible suppliers (or catalog empty) for the request."""


@dataclass(frozen=True)
class SupplierScoringResult:
    procurement_request: ProcurementRequestExtracted
    scored_suppliers: list[ScoredSupplierOut]
    top_suppliers: list[ScoredSupplierOut]
    scoring_fallback_used: bool


@dataclass(frozen=True)
class JustificationResult:
    justification: ProcurementJustificationLLM
    llm_fallback_used: bool


def _row_to_scored(row: dict[str, Any]) -> ScoredSupplierOut:
    sid = int(row["id"])
    return ScoredSupplierOut(
        supplier_id=sid,
        id=sid,
        name=str(row["name"]),
        ruc=str(row["ruc"]),
        email=str(row["email"]),
        rating=float(row["rating"]),
        extended_total_pen=float(row["extended_total_pen"]),
        bottleneck_lead_days=int(row["bottleneck_lead_days"]),
        price_score=float(row["price_score"]),
        delivery_score=float(row["delivery_score"]),
        reliability_score=float(row["reliability_score"]),
        wlc_score=float(row["wlc_score"]),
        lines=list(row.get("lines") or []),
    )


def _rows_to_scored(rows: list[dict[str, Any]]) -> list[ScoredSupplierOut]:
    return [_row_to_scored(r) for r in rows]


def normalize_supplier_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure each row has ``id`` (API may send ``supplier_id`` from Pydantic output)."""
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        if "id" not in row and "supplier_id" in row:
            row["id"] = row["supplier_id"]
        if "name" not in row and "company_name" in row:
            row["name"] = row["company_name"]
        out.append(row)
    return out


async def _rating_fallback_rows(session: AsyncSession) -> list[dict[str, Any]]:
    """Fallback when WLC pool is empty: rank active suppliers by rating only."""
    stmt = (
        select(Supplier)
        .options(selectinload(Supplier.products))
        .where(Supplier.is_active.is_(True))
        .order_by(Supplier.rating.desc(), Supplier.id.asc())
    )
    result = await session.execute(stmt)
    suppliers = result.scalars().unique().all()
    rows: list[dict[str, Any]] = []
    for sup in suppliers:
        rating = float(sup.rating)
        rows.append(
            {
                "id": sup.id,
                "name": sup.company_name,
                "ruc": sup.ruc,
                "email": sup.email,
                "rating": rating,
                "extended_total_pen": 0.0,
                "bottleneck_lead_days": 0,
                "lines": [],
                "price_score": 0.0,
                "delivery_score": 0.0,
                "reliability_score": min(1.0, rating / 10.0),
                "wlc_score": min(1.0, rating / 10.0),
            }
        )
    return rows


async def run_supplier_scoring(
    session: AsyncSession,
    request: ProcurementRequestExtracted,
    top_n: int = 3,
) -> SupplierScoringResult:
    fallback_used = False
    scored_rows: list[dict[str, Any]] = []

    try:
        aggregated = await aggregate_supplier_quotes(
            session, request, include_external=True
        )
        quotes = aggregated.quotes
        scored_rows = score_supplier_quotes(quotes)
    except Exception as e:
        logger.exception("WLC scoring failed for %s: %s", request.request_id, e)
        fallback_used = True
        scored_rows = []

    if not scored_rows:
        fallback_used = True
        scored_rows = await _rating_fallback_rows(session)

    if not scored_rows:
        raise ScoringNoSuppliersError(
            "No active suppliers available for scoring."
        )

    scored_out = _rows_to_scored(scored_rows)
    top_out = _rows_to_scored(
        [dict(r) for r in top_suppliers(scored_rows, top_n)]
    )

    return SupplierScoringResult(
        procurement_request=request,
        scored_suppliers=scored_out,
        top_suppliers=top_out,
        scoring_fallback_used=fallback_used,
    )


def build_fallback_justification(
    top_supplier_rows: list[dict[str, Any]],
    request: ProcurementRequestExtracted,
) -> ProcurementJustificationLLM:
    best = top_supplier_rows[0]
    runner_up: int | None = None
    if len(top_supplier_rows) > 1:
        runner_up = int(top_supplier_rows[1]["id"])
    wlc = float(best.get("wlc_score", 0))
    text = (
        f"Selected {best.get('name', 'supplier')} (ID {best['id']}) with highest WLC score "
        f"({wlc:.4f}) for request {request.request_id}."
    )
    return ProcurementJustificationLLM(
        recommended_supplier_id=int(best["id"]),
        justification=text,
        runner_up_supplier_id=runner_up,
    )


async def run_justification(
    ollama_client: OllamaClient,
    top_supplier_rows: list[dict[str, Any]],
    request: ProcurementRequestExtracted,
) -> JustificationResult:
    top_supplier_rows = normalize_supplier_rows(top_supplier_rows)
    pool_ids = {int(s["id"]) for s in top_supplier_rows}

    try:
        llm = await ollama_client.get_justification(top_supplier_rows, request)
        rec_id = int(llm.recommended_supplier_id)
        if rec_id not in pool_ids:
            logger.warning(
                "LLM recommended supplier %s not in pool %s; using top WLC",
                rec_id,
                pool_ids,
            )
            fallback = build_fallback_justification(top_supplier_rows, request)
            return JustificationResult(justification=fallback, llm_fallback_used=True)
        return JustificationResult(justification=llm, llm_fallback_used=False)
    except (OllamaClientError, OllamaValidationError) as e:
        logger.warning("Justification LLM failed for %s: %s", request.request_id, e)
        return JustificationResult(
            justification=build_fallback_justification(top_supplier_rows, request),
            llm_fallback_used=True,
        )
