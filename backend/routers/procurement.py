import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from limiter import limiter
from schemas.procurement_request import (
    ProcurementParseBody,
    ProcurementParseResponse,
)
from services.candidate_aggregator import aggregate_supplier_quotes
from services.ollama_client import OllamaClient, OllamaClientError, OllamaValidationError
from services.procurement_candidates import estimate_minimum_order_total

logger = logging.getLogger(__name__)

router = APIRouter()
ollama_client = OllamaClient()


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok", "router": "procurement"}


@router.post("/parse", response_model=ProcurementParseResponse)
@limiter.limit("10/minute")
async def parse_procurement_email(
    request: Request,
    body: ProcurementParseBody,
    db: AsyncSession = Depends(get_db),
) -> ProcurementParseResponse:
    try:
        extracted_request = await ollama_client.extract_entities(body.email_body)
        logger.info("Parsed procurement request: %s", extracted_request.request_id)
    except OllamaValidationError as e:
        logger.warning("Validation error in procurement parsing: %s", e)
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract valid procurement data: {e}",
        ) from e
    except OllamaClientError as e:
        logger.error("Ollama client error in procurement parsing: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Procurement parsing service unavailable: {e}",
        ) from e
    except Exception:
        logger.exception("Unexpected error in procurement parsing")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during procurement parsing",
        ) from None

    try:
        local_est = await estimate_minimum_order_total(db, list(extracted_request.items))
    except Exception:
        logger.exception("Budget estimate query failed")
        local_est = None

    sources_used: list[str] = []
    external_quote_count = 0
    external_min_total: Decimal | None = None

    if body.include_external:
        try:
            quotes = await aggregate_supplier_quotes(
                db,
                extracted_request,
                include_external=True,
                source_ids=body.source_ids,
            )
            external_quotes = [q for q in quotes if q.supplier_id < 0]
            external_quote_count = len(external_quotes)
            if external_quotes:
                external_min_total = min(q.extended_total for q in external_quotes)
                sources_used = sorted({q.company_name for q in external_quotes})
        except Exception:
            logger.exception("External catalog aggregation failed")

    candidates: list[Decimal] = [v for v in (local_est, external_min_total) if v is not None]
    est = min(candidates) if candidates else None
    budget_exceeded = est is None or est > extracted_request.constraints.max_budget

    return ProcurementParseResponse(
        **extracted_request.model_dump(),
        budget_exceeded=budget_exceeded,
        estimated_minimum_total=est,
        sources_used=sources_used,
        external_candidate_count=external_quote_count,
    )
