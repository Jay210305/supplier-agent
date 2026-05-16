from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.order_generation import OrderGenerateResult


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_orders_ping(client: TestClient) -> None:
    r = client.get("/orders/ping")
    assert r.status_code == 200
    assert r.json()["router"] == "orders"


@patch("routers.orders.generate_purchase_order", new_callable=AsyncMock)
def test_orders_generate_success(mock_gen: AsyncMock, client: TestClient) -> None:
    mock_gen.return_value = OrderGenerateResult(
        purchase_order_id=99,
        request_id="REQ-2026-042",
        supplier_id=3,
        supplier_name="TechMype Perú SAC",
        pdf_path="generated_pos/PO_REQ-2026-042_20260101_120000.pdf",
        total_amount_pen=Decimal("3539.88"),
        justification="Best WLC fit.",
        runner_up_supplier_id=1,
        scoring_snapshot=[{"id": 3, "wlc_score": 0.9}],
    )
    body = {
        "request_id": "REQ-2026-042",
        "items": [{"product": "Laptop", "quantity": 1}],
        "constraints": {"max_budget": "50000.00", "currency": "PEN", "delivery_before": None},
        "priority": "high",
    }
    r = client.post("/orders/generate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["purchase_order_id"] == 99
    assert data["supplier_id"] == 3
    assert data["pdf_path"] is not None
