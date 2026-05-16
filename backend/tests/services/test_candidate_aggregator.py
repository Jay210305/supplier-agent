"""Unit tests for `services.candidate_aggregator` external-quote synthesis."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from schemas.catalog_source import ExternalProductResult
from schemas.procurement_request import (
    ProcurementConstraints,
    ProcurementItem,
    ProcurementRequestExtracted,
)
from services.candidate_aggregator import (
    _external_results_to_quote,
    _pick_best_external_for_item,
    _virtual_supplier_id,
)


def _hit(
    *,
    name: str,
    price: str,
    lead: int = 5,
    stock: int = 100,
    moq: int = 1,
    source_id: int = 1,
    source_name: str = "External A",
    rating: str = "7.50",
    currency: str = "PEN",
) -> ExternalProductResult:
    return ExternalProductResult(
        source_id=source_id,
        source_name=source_name,
        adapter_key="mercadolibre",
        product_name=name,
        description=None,
        sku=None,
        url=None,
        image_url=None,
        unit_price=Decimal(price),
        currency=currency,
        lead_time_days=lead,
        available_stock=stock,
        minimum_order_quantity=moq,
        rating=Decimal(rating),
    )


def _request(
    qty: int = 5,
    budget: str = "10000",
    deadline: date | None = None,
) -> ProcurementRequestExtracted:
    return ProcurementRequestExtracted(
        request_id="REQ-TEST-001",
        items=[ProcurementItem(product="laptop", quantity=qty)],
        constraints=ProcurementConstraints(
            max_budget=Decimal(budget), currency="PEN", delivery_before=deadline
        ),
        priority=None,
    )


def test_virtual_supplier_id_is_always_negative() -> None:
    assert _virtual_supplier_id(7) == -7
    assert _virtual_supplier_id(-3) == -3


def test_pick_best_external_filters_stock_and_moq_and_picks_cheapest() -> None:
    item = ProcurementItem(product="laptop", quantity=5)
    hits = [
        _hit(name="Laptop A", price="1000", stock=3),  # not enough stock
        _hit(name="Laptop B", price="900", moq=10),  # moq too high
        _hit(name="Tablet C", price="500"),  # name does not match
        _hit(name="Laptop D", price="800", lead=10),
        _hit(name="Laptop E", price="850", lead=2),
    ]
    pick = _pick_best_external_for_item(item, hits)
    assert pick is not None
    assert pick.product_name == "Laptop D"


def test_pick_best_external_returns_none_when_no_candidates() -> None:
    item = ProcurementItem(product="laptop", quantity=2)
    assert _pick_best_external_for_item(item, []) is None
    assert (
        _pick_best_external_for_item(item, [_hit(name="cama", price="100")]) is None
    )


def test_external_quote_built_when_within_budget_and_deadline() -> None:
    request = _request(qty=2, budget="2000", deadline=date.today() + timedelta(days=10))
    per_query = {"laptop": [_hit(name="Laptop pro", price="800", lead=5)]}
    quote = _external_results_to_quote(
        source_id=42,
        source_name="External Pool",
        per_query=per_query,
        request=request,
        days_available=10,
    )
    assert quote is not None
    assert quote.supplier_id == -42
    assert quote.extended_total == Decimal("1600")
    assert quote.bottleneck_lead_days == 5
    assert quote.company_name.startswith("[mercadolibre]")
    assert quote.lines[0]["external_source_id"] == 42


def test_external_quote_rejected_when_over_budget() -> None:
    request = _request(qty=10, budget="1000")
    per_query = {"laptop": [_hit(name="Laptop", price="500")]}  # 10 * 500 = 5000
    quote = _external_results_to_quote(
        source_id=1,
        source_name="X",
        per_query=per_query,
        request=request,
        days_available=None,
    )
    assert quote is None


def test_external_quote_rejected_when_lead_exceeds_deadline() -> None:
    request = _request(qty=1, budget="9999", deadline=date.today() + timedelta(days=2))
    per_query = {"laptop": [_hit(name="Laptop", price="500", lead=5)]}
    quote = _external_results_to_quote(
        source_id=1,
        source_name="X",
        per_query=per_query,
        request=request,
        days_available=2,
    )
    assert quote is None


def test_external_quote_requires_all_items_covered() -> None:
    request = ProcurementRequestExtracted(
        request_id="REQ-2",
        items=[
            ProcurementItem(product="laptop", quantity=1),
            ProcurementItem(product="impresora", quantity=1),
        ],
        constraints=ProcurementConstraints(
            max_budget=Decimal("10000"), currency="PEN", delivery_before=None
        ),
        priority=None,
    )
    per_query = {
        "laptop": [_hit(name="Laptop", price="500")],
        "impresora": [],
    }
    quote = _external_results_to_quote(
        source_id=1,
        source_name="X",
        per_query=per_query,
        request=request,
        days_available=None,
    )
    assert quote is None
