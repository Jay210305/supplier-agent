from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.procurement_request import ProcurementRequestExtracted
from schemas.purchase_order import OrderGenerateResponse
from services.ollama_client import OllamaClient
from services.order_generation import (
    DuplicateRequestError,
    LLMUnavailableError,
    OrderGenerationError,
    generate_purchase_order,
)
from services.pdf_generator import POPDFGenerator

logger = logging.getLogger(__name__)

router = APIRouter()
ollama_client = OllamaClient()
pdf_generator = POPDFGenerator()


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok", "router": "orders"}


@router.post("/generate", response_model=OrderGenerateResponse)
async def generate_order(
    body: ProcurementRequestExtracted,
    db: AsyncSession = Depends(get_db),
) -> OrderGenerateResponse:
    try:
        result = await generate_purchase_order(db, body, ollama_client, pdf_generator)
    except DuplicateRequestError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except LLMUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except OrderGenerationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return OrderGenerateResponse(
        purchase_order_id=result.purchase_order_id,
        request_id=result.request_id,
        supplier_id=result.supplier_id,
        supplier_name=result.supplier_name,
        pdf_path=result.pdf_path,
        total_amount_pen=result.total_amount_pen,
        justification=result.justification,
        runner_up_supplier_id=result.runner_up_supplier_id,
        scoring_snapshot=result.scoring_snapshot,
    )
