"""Generate scored PO + PDF from a validated procurement request."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import LogSeverity, PurchaseOrderStatus
from models.procurement_log import ProcurementLog
from models.purchase_order import PurchaseOrder
from models.supplier import Supplier
from schemas.procurement_request import ProcurementJustificationLLM, ProcurementRequestExtracted
from services.ollama_client import OllamaClient, OllamaClientError, OllamaValidationError
from services.pdf_generator import POPDFGenerator, pen_line_totals
from services.procurement_candidates import build_supplier_quotes
from services.scoring import score_supplier_quotes, top_suppliers

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


async def generate_purchase_order(
    session: AsyncSession,
    request: ProcurementRequestExtracted,
    ollama_client: OllamaClient,
    pdf_gen: POPDFGenerator,
) -> OrderGenerateResult:
    dup = await session.execute(
        select(PurchaseOrder.id).where(PurchaseOrder.request_id == request.request_id).limit(1)
    )
    if dup.scalar_one_or_none() is not None:
        raise DuplicateRequestError(f"Purchase order already exists for {request.request_id}")

    quotes = await build_supplier_quotes(session, request)
    scored = score_supplier_quotes(quotes)
    if not scored:
        raise OrderGenerationError(
            "No eligible suppliers for this request (stock, budget, delivery, or catalog match)."
        )

    top3 = top_suppliers(scored, 3)
    pool_ids = {int(s["id"]) for s in top3}

    try:
        justification_llm: ProcurementJustificationLLM = await ollama_client.get_justification(
            top3, request
        )
    except OllamaClientError as e:
        raise LLMUnavailableError(str(e)) from e
    except OllamaValidationError as e:
        raise OrderGenerationError(f"Invalid justification from LLM: {e}") from e

    rec_id = int(justification_llm.recommended_supplier_id)
    if rec_id not in pool_ids:
        logger.warning(
            "LLM recommended supplier %s not in WLC top pool %s; using top-ranked",
            rec_id,
            pool_ids,
        )
        rec_id = int(top3[0]["id"])

    chosen = next(s for s in scored if int(s["id"]) == rec_id)
    supplier = await session.get(Supplier, rec_id)
    if supplier is None:
        raise OrderGenerationError(f"Supplier {rec_id} not found")

    items_for_pdf: list[dict[str, Any]] = []
    for ln in chosen["lines"]:
        items_for_pdf.append(
            {
                "product_name": ln["product_name"],
                "quantity": int(ln["quantity"]),
                "unit_price": float(Decimal(ln["unit_price"])),
            }
        )

    _subtotal, _igv, grand_total = pen_line_totals(items_for_pdf)

    payload: dict[str, Any] = {
        "procurement_request": request.model_dump(mode="json"),
        "wlc_ranking": scored[:10],
        "llm": justification_llm.model_dump(),
        "selected_supplier_id": rec_id,
    }

    po = PurchaseOrder(
        request_id=request.request_id,
        supplier_id=rec_id,
        status=PurchaseOrderStatus.PENDING,
        currency=request.constraints.currency,
        total_amount=grand_total,
        payload=payload,
        notes=justification_llm.justification[:4000],
    )
    session.add(po)
    await session.flush()

    try:
        pdf_path = pdf_gen.generate_purchase_order_pdf(po, supplier, items_for_pdf)
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
            payload={"purchase_order_id": po.id, "supplier_id": rec_id, "pdf_path": po.pdf_path},
            severity=LogSeverity.INFO,
        )
    )
    await session.commit()
    await session.refresh(po)

    return OrderGenerateResult(
        purchase_order_id=po.id,
        request_id=request.request_id,
        supplier_id=rec_id,
        supplier_name=supplier.company_name,
        pdf_path=po.pdf_path,
        total_amount_pen=grand_total,
        justification=justification_llm.justification,
        runner_up_supplier_id=justification_llm.runner_up_supplier_id,
        scoring_snapshot=scored[:10],
    )
