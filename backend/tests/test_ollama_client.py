from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from schemas.procurement_request import (
    ProcurementConstraints,
    ProcurementItem,
    ProcurementPriority,
    ProcurementRequestExtracted,
)
from services.ollama_client import OllamaClient, OllamaClientError, OllamaValidationError


@pytest.fixture
def ollama_client() -> OllamaClient:
    return OllamaClient()


@pytest.mark.asyncio
async def test_extract_entities_success(ollama_client: OllamaClient) -> None:
    data = {
        "request_id": "REQ-2026-001",
        "items": [{"product": "Laptop", "quantity": 10}],
        "constraints": {
            "max_budget": "30000.00",
            "currency": "PEN",
            "delivery_before": "2026-05-19",
        },
        "priority": "high",
    }
    with patch.object(ollama_client, "_generate_json", new_callable=AsyncMock, return_value=data):
        result = await ollama_client.extract_entities(
            "Necesito 10 laptops antes del lunes, presupuesto 30000 soles."
        )
    assert isinstance(result, ProcurementRequestExtracted)
    assert result.request_id == "REQ-2026-001"
    assert len(result.items) == 1
    assert result.items[0].product == "Laptop"
    assert result.items[0].quantity == 10
    assert result.constraints.max_budget == Decimal("30000.00")
    assert result.constraints.currency == "PEN"
    assert result.priority == ProcurementPriority.HIGH


@pytest.mark.asyncio
async def test_extract_entities_retries_then_succeeds(ollama_client: OllamaClient) -> None:
    bad = {"request_id": "X", "items": [{"product": "Laptop", "quantity": 1}]}
    good = {
        "request_id": "REQ-2026-001",
        "items": [{"product": "Laptop", "quantity": 10}],
        "constraints": {"max_budget": "30000.00", "currency": "PEN", "delivery_before": None},
        "priority": "high",
    }
    with patch.object(
        ollama_client,
        "_generate_json",
        new_callable=AsyncMock,
        side_effect=[bad, good],
    ):
        result = await ollama_client.extract_entities("email body")
    assert result.request_id == "REQ-2026-001"


@pytest.mark.asyncio
async def test_extract_entities_invalid_twice(ollama_client: OllamaClient) -> None:
    bad = {"request_id": "X", "items": [{"product": "Laptop", "quantity": 1}]}
    with patch.object(
        ollama_client,
        "_generate_json",
        new_callable=AsyncMock,
        side_effect=[bad, bad],
    ):
        with pytest.raises(OllamaValidationError):
            await ollama_client.extract_entities("Test email")


@pytest.mark.asyncio
async def test_extract_entities_ollama_error(ollama_client: OllamaClient) -> None:
    with patch.object(
        ollama_client,
        "_generate_json",
        new_callable=AsyncMock,
        side_effect=OllamaClientError("Service unavailable"),
    ):
        with pytest.raises(OllamaClientError):
            await ollama_client.extract_entities("Test email")


def test_entity_extraction_prompt_file(ollama_client: OllamaClient) -> None:
    text = ollama_client._prompt_file("entity_extraction.txt")
    assert "procurement assistant" in text.lower()
    assert "request_id" in text
    assert "items" in text


def test_justification_prompt_file(ollama_client: OllamaClient) -> None:
    text = ollama_client._prompt_file("justification.txt")
    assert "recommended_supplier_id" in text.lower() or "json" in text.lower()
