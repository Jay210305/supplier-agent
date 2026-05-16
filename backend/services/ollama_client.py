from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from config import settings
from schemas.procurement_request import ProcurementJustificationLLM, ProcurementRequestExtracted

logger = logging.getLogger(__name__)

_STRICT_JSON_SUFFIX = """
CRITICAL — SECOND ATTEMPT RULES:
- Return ONE JSON object only. No markdown, no code fences, no text before or after.
- Schema (all top-level keys required): request_id (string), items (array of {product, quantity}),
  constraints (object with max_budget number, currency 3-letter string, delivery_before YYYY-MM-DD or null),
  priority: one of "low" | "medium" | "high" or null.
Example (structure only):
{"request_id":"REQ-2026-001","items":[{"product":"Laptop","quantity":10}],"constraints":{"max_budget":30000.00,"currency":"PEN","delivery_before":"2026-05-19"},"priority":"high"}
"""


class OllamaClientError(Exception):
    """Ollama HTTP/network or unavailable."""


class OllamaValidationError(Exception):
    """Malformed JSON or failed Pydantic validation on model output."""


class OllamaClient:
    def __init__(self) -> None:
        self.timeout = 120.0

    def _prompt_file(self, filename: str) -> str:
        path: Path = settings.prompts_dir / filename
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            logger.warning("Prompt file missing at %s, using inline fallback", path)
            return self._fallback_entity_prompt() if filename == "entity_extraction.txt" else self._fallback_justification_prompt()

    def _fallback_entity_prompt(self) -> str:
        return (
            "You are a procurement assistant. Extract structured data from the email.\n"
            "Return ONLY valid JSON with keys: request_id, items, constraints, priority.\n"
            "See project prompts/entity_extraction.txt for the full specification."
        )

    def _fallback_justification_prompt(self) -> str:
        return (
            "You are a procurement assistant. Return ONLY JSON with recommended_supplier_id, "
            "justification, runner_up_supplier_id (or null)."
        )

    async def _generate_json(self, prompt: str) -> dict[str, Any]:
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        url = f"{base}/api/generate"
        payload: dict[str, Any] = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_ctx": 4096},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Ollama HTTP error: %s - %s", e.response.status_code, e.response.text
                )
                raise OllamaClientError(
                    f"Ollama service error: {e.response.status_code}"
                ) from e
            except httpx.RequestError as e:
                logger.error("Ollama request error: %s", e)
                raise OllamaClientError(f"Failed to connect to Ollama: {e}") from e

        text = (body.get("response") or "").strip()
        if not text:
            raise OllamaValidationError("Empty response from Ollama")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON from Ollama: %s", text[:500])
            raise OllamaValidationError(f"Invalid JSON in Ollama response: {e}") from e

    def _validate_procurement(self, data: dict[str, Any]) -> ProcurementRequestExtracted:
        try:
            return ProcurementRequestExtracted.model_validate(data)
        except Exception as e:
            logger.warning("Pydantic validation failed: %s data=%s", e, data)
            raise OllamaValidationError(f"Validation error: {e}") from e

    async def extract_entities(self, email_body: str) -> ProcurementRequestExtracted:
        prompt_base = self._prompt_file("entity_extraction.txt")
        prompts = (prompt_base, f"{prompt_base}{_STRICT_JSON_SUFFIX}")
        last_val_err: OllamaValidationError | None = None

        for prompt in prompts:
            full_prompt = f"{prompt}\n\nEMAIL:\n{email_body}"
            try:
                data = await self._generate_json(full_prompt)
                return self._validate_procurement(data)
            except OllamaClientError:
                raise
            except OllamaValidationError as e:
                last_val_err = e
                continue

        assert last_val_err is not None
        raise last_val_err

    async def get_justification(
        self,
        top_suppliers: list[dict[str, Any]],
        procurement_request: ProcurementRequestExtracted,
    ) -> ProcurementJustificationLLM:
        prompt_template = self._prompt_file("justification.txt")
        suppliers_text = "\n".join(
            (
                f"Supplier ID: {s['id']}, Name: {s['name']}, "
                f"Unit Price: {s.get('unit_price', 'N/A')}, "
                f"Lead Time: {s.get('lead_time_days', 'N/A')} days, "
                f"Rating: {s.get('rating', 'N/A')}/10"
            )
            for s in top_suppliers
        )
        items_text = "\n".join(
            f"- {item.product}: {item.quantity}" for item in procurement_request.items
        )
        constraints = procurement_request.constraints
        full_prompt = f"""{prompt_template}

PROCUREMENT REQUEST:
Request ID: {procurement_request.request_id}
Items:
{items_text}
Constraints:
- Max Budget: {constraints.max_budget} {constraints.currency}
- Delivery Before: {constraints.delivery_before or "Not specified"}
- Priority: {procurement_request.priority or "Not specified"}

TOP 3 SUPPLIERS (from WLC scoring):
{suppliers_text}

Respond in the exact JSON format specified in the system instructions."""

        data = await self._generate_json(full_prompt)
        if "runner_up_supplier_id" not in data:
            data["runner_up_supplier_id"] = None
        try:
            return ProcurementJustificationLLM.model_validate(data)
        except Exception as e:
            raise OllamaValidationError(f"Justification validation error: {e}") from e
