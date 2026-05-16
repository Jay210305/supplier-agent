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
        "supplier_id": 3,
        "items": [{"product": "Laptop", "quantity": 1}],
        "constraints": {"max_budget": "50000.00", "currency": "PEN", "delivery_before": None},
        "priority": "high",
        "justification": "Pre-selected by n8n scoring flow.",
    }
    r = client.post("/orders/generate", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["purchase_order_id"] == 99
    assert data["supplier_id"] == 3
    assert data["pdf_path"] is not None


@patch("routers.orders.approve_purchase_order", new_callable=AsyncMock)
def test_orders_approve_success(mock_approve: AsyncMock, client: TestClient) -> None:
    from models.enums import PurchaseOrderStatus
    from schemas.purchase_order import OrderApproveResponse

    mock_approve.return_value = OrderApproveResponse(
        purchase_order_id=99,
        request_id="REQ-2026-042",
        status=PurchaseOrderStatus.APPROVED,
        approved_by="manager@mype.com.pe",
        pdf_path="generated_pos/PO_REQ-2026-042.pdf",
        total_amount=Decimal("3539.88"),
        currency="PEN",
    )
    r = client.patch(
        "/orders/REQ-2026-042/approve",
        json={"status": "Approved", "approved_by": "manager@mype.com.pe"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"


@patch("routers.orders.approve_purchase_order", new_callable=AsyncMock)
def test_orders_approve_not_found(mock_approve: AsyncMock, client: TestClient) -> None:
    from services.order_approval import PurchaseOrderNotFoundError

    mock_approve.side_effect = PurchaseOrderNotFoundError("missing")
    r = client.patch("/orders/REQ-MISSING/approve", json={"status": "Approved"})
    assert r.status_code == 404
