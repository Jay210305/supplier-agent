from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from schemas.procurement_request import (
    ProcurementConstraints,
    ProcurementItem,
    ProcurementPriority,
    ProcurementRequestExtracted,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_procurement_ping(client: TestClient) -> None:
    response = client.get("/procurement/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "router": "procurement"}


@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_procurement_email_success(mock_extract: AsyncMock, client: TestClient) -> None:
    mock_request = ProcurementRequestExtracted(
        request_id="REQ-2026-001",
        items=[ProcurementItem(product="Laptop", quantity=10)],
        constraints=ProcurementConstraints(
            max_budget=Decimal("30000.00"),
            currency="PEN",
            delivery_before=None,
        ),
        priority=ProcurementPriority.HIGH,
    )
    mock_extract.return_value = mock_request

    response = client.post(
        "/procurement/parse",
        json={"email_body": "Necesito 10 laptops antes del lunes, presupuesto 30000 soles."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "REQ-2026-001"
    assert len(data["items"]) == 1
    assert data["items"][0]["product"] == "Laptop"
    assert data["items"][0]["quantity"] == 10
    assert data["constraints"]["max_budget"] == 30000.0
    assert data["constraints"]["currency"] == "PEN"
    assert data["priority"] == "high"


@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_procurement_email_validation_error(mock_extract: AsyncMock, client: TestClient) -> None:
    from services.ollama_client import OllamaValidationError

    mock_extract.side_effect = OllamaValidationError("Invalid response format")
    response = client.post(
        "/procurement/parse",
        json={"email_body": "Invalid email content"},
    )
    assert response.status_code == 422
    assert "Failed to extract valid procurement data" in response.json()["detail"]


@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_procurement_email_ollama_error(mock_extract: AsyncMock, client: TestClient) -> None:
    from services.ollama_client import OllamaClientError

    mock_extract.side_effect = OllamaClientError("Service unavailable")
    response = client.post(
        "/procurement/parse",
        json={"email_body": "Test email"},
    )
    assert response.status_code == 503
    assert "Procurement parsing service unavailable" in response.json()["detail"]


@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_rate_limit(mock_extract: AsyncMock, client: TestClient) -> None:
    mock_extract.return_value = ProcurementRequestExtracted(
        request_id="REQ-2026-001",
        items=[ProcurementItem(product="Laptop", quantity=10)],
        constraints=ProcurementConstraints(
            max_budget=Decimal("30000.00"),
            currency="PEN",
            delivery_before=None,
        ),
        priority=ProcurementPriority.HIGH,
    )
    for _ in range(10):
        r = client.post("/procurement/parse", json={"email_body": "x"})
        assert r.status_code == 200
    blocked = client.post("/procurement/parse", json={"email_body": "x"})
    assert blocked.status_code == 429
