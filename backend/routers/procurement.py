import logging

from fastapi import APIRouter, HTTPException, Request

from limiter import limiter
from schemas.procurement_request import ProcurementParseBody, ProcurementRequestExtracted
from services.ollama_client import OllamaClient, OllamaClientError, OllamaValidationError

logger = logging.getLogger(__name__)

router = APIRouter()
ollama_client = OllamaClient()


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok", "router": "procurement"}


@router.post("/parse", response_model=ProcurementRequestExtracted)
@limiter.limit("10/minute")
async def parse_procurement_email(
    request: Request,
    body: ProcurementParseBody,
):
    try:
        extracted_request = await ollama_client.extract_entities(body.email_body)
        logger.info("Parsed procurement request: %s", extracted_request.request_id)
        return extracted_request
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