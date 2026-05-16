"""Unit tests for scoring_workflow (Phase 6)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from schemas.procurement_request import (
    ProcurementConstraints,
    ProcurementItem,
    ProcurementRequestExtracted,
)
from services.ollama_client import OllamaClientError
from services.scoring_workflow import (
    build_fallback_justification,
    run_justification,
)


def _request() -> ProcurementRequestExtracted:
    return ProcurementRequestExtracted(
        request_id="REQ-2026-001",
        items=[ProcurementItem(product="Laptop", quantity=10)],
        constraints=ProcurementConstraints(
            max_budget=Decimal("30000"), currency="PEN", delivery_before=None
        ),
        priority=None,
    )


def test_build_fallback_justification() -> None:
    top = [
        {"id": 2, "name": "Supplier B", "wlc_score": 0.447},
        {"id": 1, "name": "Supplier A", "wlc_score": 0.36},
    ]
    j = build_fallback_justification(top, _request())
    assert j.recommended_supplier_id == 2
    assert j.runner_up_supplier_id == 1
    assert "WLC" in j.justification


@pytest.mark.asyncio
async def test_run_justification_ollama_fallback() -> None:
    top = [{"id": 5, "name": "FastCo", "wlc_score": 0.8}]
    ollama = MagicMock()
    ollama.get_justification = AsyncMock(side_effect=OllamaClientError("down"))
    outcome = await run_justification(ollama, top, _request())
    assert outcome.llm_fallback_used is True
    assert outcome.justification.recommended_supplier_id == 5
