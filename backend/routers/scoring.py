from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.scoring import (
    JustificationBody,
    JustificationResponse,
    ScoreSuppliersBody,
    ScoreSuppliersResponse,
)
from services.ollama_client import OllamaClient
from services.scoring_workflow import (
    ScoringNoSuppliersError,
    run_justification,
    run_supplier_scoring,
)

logger = logging.getLogger(__name__)

router = APIRouter()
ollama_client = OllamaClient()


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok", "router": "scoring"}


@router.post("/score_suppliers", response_model=ScoreSuppliersResponse)
async def score_suppliers(
    body: ScoreSuppliersBody,
    db: AsyncSession = Depends(get_db),
) -> ScoreSuppliersResponse:
    """Rank eligible suppliers by WLC; fetches catalog from Postgres (Option A)."""
    try:
        result = await run_supplier_scoring(
            db, body.procurement_request, top_n=body.top_n
        )
    except ScoringNoSuppliersError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("score_suppliers failed: %s", e)
        raise HTTPException(
            status_code=503, detail="Scoring service temporarily unavailable"
        ) from e

    return ScoreSuppliersResponse(
        procurement_request=result.procurement_request,
        scored_suppliers=result.scored_suppliers,
        top_suppliers=result.top_suppliers,
        scoring_fallback_used=result.scoring_fallback_used,
    )


@router.post("/justification", response_model=JustificationResponse)
async def justification(
    body: JustificationBody,
) -> JustificationResponse:
    """LLM recommendation among top suppliers; falls back to top WLC on failure."""
    req = body.procurement_request
    try:
        outcome = await run_justification(ollama_client, body.top_suppliers, req)
    except Exception as e:
        logger.exception("justification failed: %s", e)
        raise HTTPException(
            status_code=503, detail="Justification service temporarily unavailable"
        ) from e

    j = outcome.justification
    return JustificationResponse(
        recommended_supplier_id=j.recommended_supplier_id,
        justification=j.justification,
        runner_up_supplier_id=j.runner_up_supplier_id,
        llm_fallback_used=outcome.llm_fallback_used,
        request_id=req.request_id,
        items=req.items,
        constraints=req.constraints,
        priority=req.priority,
    )
