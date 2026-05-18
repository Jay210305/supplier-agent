from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from schemas.catalog_source import MarketplaceListing
from schemas.procurement_request import (
    ProcurementConstraints,
    ProcurementItem,
    ProcurementRequestExtracted,
)
from services.candidate_aggregator import _pick_best_external_for_item
from services.marketplace_fulfillment import build_quotes_from_market_snapshot
from schemas.catalog_source import ExternalProductResult


def _hit(name: str, price: str, *, product: str = "PlayStation") -> ExternalProductResult:
    return ExternalProductResult(
        source_id=8,
        source_name="ScraperAPI (Amazon US)",
        adapter_key="scraperapi",
        product_name=name,
        unit_price=Decimal(price),
        currency="USD",
        lead_time_days=10,
        available_stock=9999,
        minimum_order_quantity=1,
        rating=Decimal("7.50"),
    )


def test_external_pick_falls_back_without_title_token_match() -> None:
    item = ProcurementItem(product="PlayStation", quantity=1)
    hits = [
        _hit("Sony PlayStation 5 Console", "499.99"),
        _hit("Random accessory", "19.99"),
    ]
    pick = _pick_best_external_for_item(item, hits)
    assert pick is not None
    assert "PlayStation 5" in pick.product_name


def test_build_quotes_from_snapshot_covers_unknown_local_product() -> None:
    request = ProcurementRequestExtracted(
        request_id="REQ-MKT-001",
        items=[ProcurementItem(product="PlayStation", quantity=2)],
        constraints=ProcurementConstraints(
            max_budget=Decimal("50000"),
            currency="PEN",
            delivery_before=date.today() + timedelta(days=14),
        ),
        priority=None,
    )
    snapshot = [
        MarketplaceListing(
            source_id=8,
            source_name="ScraperAPI (Amazon US)",
            adapter_key="scraperapi",
            query="PlayStation",
            product_name="Sony PS5 Console",
            unit_price=Decimal("499.99"),
            currency="USD",
            url="https://www.amazon.com/dp/example",
            lead_time_days=10,
        )
    ]
    quotes = build_quotes_from_market_snapshot(
        snapshot, request, days_available=14
    )
    assert len(quotes) == 1
    assert quotes[0].supplier_id == -8
    assert quotes[0].extended_total == Decimal("999.98")
