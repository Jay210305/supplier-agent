"""Generate scored PO + PDF from a validated procurement request."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import LogSeverity, PurchaseOrderStatus
from models.procurement_log import ProcurementLog
from models.purchase_order import PurchaseOrder
from models.supplier import Supplier
from schemas.procurement_request import ProcurementJustificationLLM, ProcurementRequestExtracted
from schemas.purchase_order import OrderGenerateBody
from services.candidate_aggregator import aggregate_supplier_quotes
from services.marketplace_fulfillment import (
    build_quotes_from_market_snapshot,
    get_marketplace_placeholder_supplier,
    is_virtual_supplier_id,
    supplier_pdf_view,
    virtual_catalog_source_id,
)
from services.ollama_client import OllamaClient
from services.pdf_generator import POPDFGenerator, pen_line_totals
from services.scoring import score_supplier_quotes, top_suppliers
from services.scoring_workflow import build_fallback_justification, run_justification

logger = logging.getLogger(__name__)


class DuplicateRequestError(Exception):
    """request_id already has a purchase order."""


class LLMUnavailableError(Exception):
    """Ollama unreachable or HTTP error."""


class OrderGenerationError(Exception):
    """Business rule failure (no suppliers, bad LLM output, PDF error)."""


@dataclass
class OrderGenerateResult:
    purchase_order_id: int
    request_id: str
    supplier_id: int
    supplier_name: str
    pdf_path: str | None
    total_amount_pen: Decimal
    justification: str
    runner_up_supplier_id: int | None
    scoring_snapshot: list[dict[str, Any]]


async def _collect_eligible_quotes(
    session: AsyncSession,
    request: ProcurementRequestExtracted,
    body: OrderGenerateBody,
) -> list:
    """Local DB + live marketplace adapters + optional snapshot fallback."""
    aggregated = await aggregate_supplier_quotes(session, request, include_external=True)
    quotes = list(aggregated.quotes)

    snapshot = body.external_market_snapshot or []
    if snapshot and not any(q.supplier_id < 0 for q in quotes):
        deadline = request.constraints.delivery_before
        today = datetime.now(timezone.utc).date()
        days_available = (deadline - today).days if deadline is not None else None
        quotes.extend(
            build_quotes_from_market_snapshot(
                snapshot, request, days_available=days_available
            )
        )

    return quotes


async def generate_purchase_order(
    session: AsyncSession,
    body: OrderGenerateBody,
    ollama_client: OllamaClient,
    pdf_gen: POPDFGenerator,
) -> OrderGenerateResult:
    request = ProcurementRequestExtracted.model_validate(body.model_dump())
    dup = await session.execute(
        select(PurchaseOrder.id).where(PurchaseOrder.request_id == request.request_id).limit(1)
    )
    if dup.scalar_one_or_none() is not None:
        raise DuplicateRequestError(f"Purchase order already exists for {request.request_id}")

    quotes = await _collect_eligible_quotes(session, request, body)
    scored = score_supplier_quotes(quotes)
    if not scored:
        raise OrderGenerationError(
            "No eligible suppliers for this request. Enable marketplace catalog sources "
            "(ScraperAPI) and/or ensure local seed products match, or pass "
            "external_market_snapshot from /procurement/parse."
        )

    snapshot = body.scoring_snapshot if body.scoring_snapshot is not None else scored[:10]

    if body.supplier_id is not None:
        rec_id = int(body.supplier_id)
        chosen = next((s for s in scored if int(s["id"]) == rec_id), None)
        if chosen is None:
            raise OrderGenerationError(
                f"Supplier {rec_id} is not eligible for this request."
            )
        if body.justification:
            justification_llm = ProcurementJustificationLLM(
                recommended_supplier_id=rec_id,
                justification=body.justification,
                runner_up_supplier_id=body.runner_up_supplier_id,
            )
        else:
            justification_llm = build_fallback_justification(
                [chosen], request
            )
    else:
        top3 = top_suppliers(scored, 3)
        try:
            outcome = await run_justification(ollama_client, top3, request)
            justification_llm = outcome.justification
        except Exception as e:
            raise LLMUnavailableError(str(e)) from e

        rec_id = int(justification_llm.recommended_supplier_id)
        pool_ids = {int(s["id"]) for s in top3}
        if rec_id not in pool_ids:
            logger.warning(
                "Recommended supplier %s not in WLC top pool %s; using top-ranked",
                rec_id,
                pool_ids,
            )
            rec_id = int(top3[0]["id"])
        chosen = next(s for s in scored if int(s["id"]) == rec_id)

    virtual_id: int | None = rec_id if is_virtual_supplier_id(rec_id) else None
    if virtual_id is not None:
        db_supplier = await get_marketplace_placeholder_supplier(session)
        db_supplier_id = db_supplier.id
    else:
        db_supplier = await session.get(Supplier, rec_id)
        if db_supplier is None:
            raise OrderGenerationError(f"Supplier {rec_id} not found")
        db_supplier_id = rec_id

    pdf_supplier = supplier_pdf_view(
        db_supplier, chosen=chosen, virtual_supplier_id=virtual_id
    )

    items_for_pdf: list[dict[str, Any]] = []
    for ln in chosen["lines"]:
        items_for_pdf.append(
            {
                "product_name": ln["product_name"],
                "quantity": int(ln["quantity"]),
                "unit_price": float(Decimal(ln["unit_price"])),
                "currency": ln.get("currency", request.constraints.currency),
            }
        )

    _subtotal, _igv, grand_total = pen_line_totals(items_for_pdf)

    payload: dict[str, Any] = {
        "procurement_request": request.model_dump(mode="json"),
        "wlc_ranking": snapshot,
        "llm": justification_llm.model_dump(),
        "selected_supplier_id": rec_id,
    }
    if virtual_id is not None:
        payload["fulfillment"] = {
            "type": "external_marketplace",
            "catalog_source_id": virtual_catalog_source_id(virtual_id),
            "display_supplier_name": chosen["name"],
            "virtual_supplier_id": virtual_id,
        }
    if body.external_market_snapshot:
        payload["external_market_snapshot"] = [
            listing.model_dump(mode="json") for listing in body.external_market_snapshot
        ]

    po = PurchaseOrder(
        request_id=request.request_id,
        supplier_id=db_supplier_id,
        status=PurchaseOrderStatus.PENDING,
        currency=request.constraints.currency,
        total_amount=grand_total,
        payload=payload,
        notes=justification_llm.justification[:4000],
    )
    session.add(po)
    await session.flush()

    try:
        pdf_path = pdf_gen.generate_purchase_order_pdf(
            po, pdf_supplier, items_for_pdf
        )
        po.pdf_path = pdf_path
    except Exception as e:
        logger.exception("PDF generation failed: %s", e)
        await session.rollback()
        raise OrderGenerationError(f"PDF generation failed: {e}") from e

    session.add(
        ProcurementLog(
            event_type="PO_GENERATED",
            event_source="orders.generate",
            message=f"PO draft id={po.id} request={request.request_id}",
            payload={
                "purchase_order_id": po.id,
                "supplier_id": rec_id,
                "db_supplier_id": db_supplier_id,
                "pdf_path": po.pdf_path,
            },
            severity=LogSeverity.INFO,
        )
    )
    await session.commit()
    await session.refresh(po)

    display_name = (
        str(chosen["name"]) if virtual_id is not None else db_supplier.company_name
    )

    return OrderGenerateResult(
        purchase_order_id=po.id,
        request_id=request.request_id,
        supplier_id=rec_id,
        supplier_name=display_name,
        pdf_path=po.pdf_path,
        total_amount_pen=grand_total,
        justification=justification_llm.justification,
        runner_up_supplier_id=justification_llm.runner_up_supplier_id,
        scoring_snapshot=snapshot,
    )
