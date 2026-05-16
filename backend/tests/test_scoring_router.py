from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from schemas.procurement_request import ProcurementJustificationLLM
from schemas.scoring import ScoredSupplierOut
from services.scoring_workflow import JustificationResult, SupplierScoringResult


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _procurement_body() -> dict:
    return {
        "procurement_request": {
            "request_id": "REQ-2026-001",
            "items": [{"product": "Laptop", "quantity": 10}],
            "constraints": {
                "max_budget": "30000.00",
                "currency": "PEN",
                "delivery_before": "2026-05-19",
            },
            "priority": "high",
        },
        "top_n": 3,
    }


def test_scoring_ping(client: TestClient) -> None:
    r = client.get("/scoring/ping")
    assert r.status_code == 200
    assert r.json()["router"] == "scoring"


@patch("routers.scoring.run_supplier_scoring", new_callable=AsyncMock)
def test_score_suppliers_success(mock_score: AsyncMock, client: TestClient) -> None:
    from schemas.procurement_request import (
        ProcurementConstraints,
        ProcurementItem,
        ProcurementRequestExtracted,
    )

    req = ProcurementRequestExtracted(
        request_id="REQ-2026-001",
        items=[ProcurementItem(product="Laptop", quantity=10)],
        constraints=ProcurementConstraints(
            max_budget=Decimal("30000"), currency="PEN", delivery_before=None
        ),
        priority=None,
    )
    row = ScoredSupplierOut(
        supplier_id=2,
        name="B",
        ruc="20123456781",
        email="b@y.pe",
        rating=9.0,
        extended_total_pen=30000.0,
        bottleneck_lead_days=1,
        price_score=0.0,
        delivery_score=0.667,
        reliability_score=0.9,
        wlc_score=0.447,
        lines=[],
    )
    mock_score.return_value = SupplierScoringResult(
        procurement_request=req,
        scored_suppliers=[row],
        top_suppliers=[row],
        scoring_fallback_used=False,
    )
    r = client.post("/scoring/score_suppliers", json=_procurement_body())
    assert r.status_code == 200
    data = r.json()
    assert data["top_suppliers"][0]["supplier_id"] == 2
    assert data["scoring_fallback_used"] is False


@patch("routers.scoring.run_supplier_scoring", new_callable=AsyncMock)
def test_score_suppliers_no_suppliers(mock_score: AsyncMock, client: TestClient) -> None:
    from services.scoring_workflow import ScoringNoSuppliersError

    mock_score.side_effect = ScoringNoSuppliersError("none")
    r = client.post("/scoring/score_suppliers", json=_procurement_body())
    assert r.status_code == 422


@patch("routers.scoring.run_justification", new_callable=AsyncMock)
def test_justification_success(mock_just: AsyncMock, client: TestClient) -> None:
    mock_just.return_value = JustificationResult(
        justification=ProcurementJustificationLLM(
            recommended_supplier_id=12,
            justification="Best fit for Monday deadline.",
            runner_up_supplier_id=7,
        ),
        llm_fallback_used=False,
    )
    body = {
        "procurement_request": _procurement_body()["procurement_request"],
        "top_suppliers": [
            {
                "id": 12,
                "name": "OfficeSupply",
                "wlc_score": 0.9,
                "extended_total_pen": 25000,
                "bottleneck_lead_days": 1,
                "rating": 8.5,
            }
        ],
    }
    r = client.post("/scoring/justification", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["recommended_supplier_id"] == 12
    assert data["request_id"] == "REQ-2026-001"
    assert data["llm_fallback_used"] is False


@patch("routers.scoring.run_justification", new_callable=AsyncMock)
def test_justification_fallback_flag(mock_just: AsyncMock, client: TestClient) -> None:
    mock_just.return_value = JustificationResult(
        justification=ProcurementJustificationLLM(
            recommended_supplier_id=12,
            justification="WLC fallback.",
            runner_up_supplier_id=None,
        ),
        llm_fallback_used=True,
    )
    body = {
        "procurement_request": _procurement_body()["procurement_request"],
        "top_suppliers": [{"id": 12, "name": "X", "wlc_score": 0.5}],
    }
    r = client.post("/scoring/justification", json=body)
    assert r.status_code == 200
    assert r.json()["llm_fallback_used"] is True
