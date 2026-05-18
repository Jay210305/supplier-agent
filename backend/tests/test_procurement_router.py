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


@patch("routers.procurement.aggregate_supplier_quotes", new_callable=AsyncMock)
@patch("routers.procurement.estimate_minimum_order_total", new_callable=AsyncMock)
@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_procurement_email_success(
    mock_extract: AsyncMock,
    mock_est: AsyncMock,
    mock_agg: AsyncMock,
    client: TestClient,
) -> None:
    from services.candidate_aggregator import AggregatedCandidates

    mock_agg.return_value = AggregatedCandidates(quotes=[])
    mock_est.return_value = Decimal("25000.00")
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
    assert data["budget_exceeded"] is False
    assert data["estimated_minimum_total"] == 25000.0


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


@patch("routers.procurement.aggregate_supplier_quotes", new_callable=AsyncMock)
@patch("routers.procurement.estimate_minimum_order_total", new_callable=AsyncMock)
@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_sources_used_lists_scraperapi_first(
    mock_extract: AsyncMock,
    mock_est: AsyncMock,
    mock_agg: AsyncMock,
    client: TestClient,
) -> None:
    from services.scoring import SupplierQuote

    mock_est.return_value = Decimal("25000.00")
    mock_extract.return_value = ProcurementRequestExtracted(
        request_id="REQ-2026-002",
        items=[ProcurementItem(product="Laptop", quantity=10)],
        constraints=ProcurementConstraints(
            max_budget=Decimal("30000.00"),
            currency="PEN",
            delivery_before=None,
        ),
        priority=ProcurementPriority.HIGH,
    )

    def _q(supplier_id: int, name: str, total: str) -> SupplierQuote:
        return SupplierQuote(
            supplier_id=supplier_id,
            company_name=name,
            ruc="00000000000",
            email=f"external+{abs(supplier_id)}@catalog.local",
            rating=Decimal("7.00"),
            extended_total=Decimal(total),
            bottleneck_lead_days=5,
            lines=(),
        )

    from services.candidate_aggregator import AggregatedCandidates

    mock_agg.return_value = AggregatedCandidates(
        quotes=[
            _q(-1, "[mercadolibre] MercadoLibre Perú", "20000"),
            _q(-2, "[scraperapi] ScraperAPI (MercadoLibre PE)", "18000"),
            _q(-3, "[generic_http] Linio Perú", "21000"),
        ],
    )

    response = client.post(
        "/procurement/parse",
        json={"email_body": "Necesito 10 laptops antes del lunes, presupuesto 30000 soles."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["external_candidate_count"] == 3
    assert data["sources_used"][0].startswith("[scraperapi]")
    assert data["estimated_minimum_total"] == 18000.0
    assert data["external_market_snapshot"] == []


@patch("routers.procurement.aggregate_supplier_quotes", new_callable=AsyncMock)
@patch("routers.procurement.estimate_minimum_order_total", new_callable=AsyncMock)
@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_returns_market_snapshot(
    mock_extract: AsyncMock,
    mock_est: AsyncMock,
    mock_agg: AsyncMock,
    client: TestClient,
) -> None:
    from schemas.catalog_source import MarketplaceListing
    from services.candidate_aggregator import AggregatedCandidates

    mock_est.return_value = Decimal("25000.00")
    mock_extract.return_value = ProcurementRequestExtracted(
        request_id="REQ-2026-003",
        items=[ProcurementItem(product="PlayStation 5", quantity=1)],
        constraints=ProcurementConstraints(
            max_budget=Decimal("30000.00"), currency="PEN", delivery_before=None
        ),
        priority=ProcurementPriority.MEDIUM,
    )
    mock_agg.return_value = AggregatedCandidates(
        quotes=[],
        market_snapshot=[
            MarketplaceListing(
                source_id=1,
                source_name="ScraperAPI (MercadoLibre PE)",
                adapter_key="scraperapi",
                query="PlayStation 5",
                product_name="Sony PS5 Slim 1TB",
                unit_price=Decimal("2599.00"),
                currency="PEN",
                url="https://articulo.mercadolibre.com.pe/MPE-1234",
                lead_time_days=5,
            ),
            MarketplaceListing(
                source_id=2,
                source_name="ScraperAPI (Amazon US)",
                adapter_key="scraperapi",
                query="PlayStation 5",
                product_name="PlayStation 5 Console",
                unit_price=Decimal("499.99"),
                currency="USD",
                url="https://www.amazon.com/dp/B0BCNKKZ91",
                lead_time_days=10,
            ),
        ],
    )

    response = client.post(
        "/procurement/parse",
        json={"email_body": "Necesito 1 PlayStation 5, presupuesto 30000 soles."},
    )
    assert response.status_code == 200
    data = response.json()
    snapshot = data["external_market_snapshot"]
    assert len(snapshot) == 2
    assert {row["source_name"] for row in snapshot} == {
        "ScraperAPI (MercadoLibre PE)",
        "ScraperAPI (Amazon US)",
    }
    assert snapshot[0]["query"] == "PlayStation 5"
    assert snapshot[0]["unit_price"] == 2599.0


@patch("routers.procurement.estimate_minimum_order_total", new_callable=AsyncMock)
@patch("routers.procurement.ollama_client.extract_entities", new_callable=AsyncMock)
def test_parse_rate_limit(mock_extract: AsyncMock, mock_est: AsyncMock, client: TestClient) -> None:
    mock_est.return_value = Decimal("1.00")
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
