"""Unit tests for WLC scoring (Phase 4)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from services.scoring import SupplierQuote, score_supplier_quotes, top_suppliers, wlc_components


def _quote(
    sid: int,
    name: str,
    ext: str,
    lead: int,
    rating: str,
) -> SupplierQuote:
    return SupplierQuote(
        supplier_id=sid,
        company_name=name,
        ruc="20123456781",
        email="x@y.pe",
        rating=Decimal(rating),
        extended_total=Decimal(ext),
        bottleneck_lead_days=lead,
        lines=(),
    )


def test_wlc_components_phase4_example() -> None:
    """Numeric check from Guidance/4_phase.md (single-line totals as 'price')."""
    ps, ds, rs, wlc = wlc_components(
        extended_total=Decimal("30000"),
        bottleneck_lead_days=1,
        reliability_rating=9.0,
        max_price=Decimal("30000"),
        max_lead_time=3,
    )
    assert abs(ps - 0.0) < 1e-9
    assert abs(ds - (1 - 1 / 3)) < 1e-9
    assert abs(rs - 0.9) < 1e-9
    expected = 0.4 * ps + 0.4 * ds + 0.2 * rs
    assert abs(wlc - expected) < 1e-6


def test_wlc_components_zero_max_price() -> None:
    ps, ds, rs, _ = wlc_components(Decimal("100"), 2, 5.0, Decimal("0"), 10)
    assert ps == 0.0
    assert 0 <= rs <= 1


def test_wlc_components_zero_max_lead_nonzero_supplier_lead() -> None:
    ps, ds, rs, _ = wlc_components(Decimal("10"), 2, 8.0, Decimal("20"), 0)
    assert ds == 0.0


def test_wlc_components_zero_max_lead_zero_supplier_lead() -> None:
    _, ds, _, _ = wlc_components(Decimal("10"), 0, 8.0, Decimal("20"), 0)
    assert ds == 1.0


def test_score_ranking_phase4_three_suppliers() -> None:
    """Guidance § example: B > A > C."""
    quotes = [
        _quote(1, "A", "25000", 2, "8.0"),
        _quote(2, "B", "30000", 1, "9.0"),
        _quote(3, "C", "28000", 3, "7.0"),
    ]
    ranked = score_supplier_quotes(quotes)
    assert [r["id"] for r in ranked] == [2, 1, 3]
    assert ranked[0]["wlc_score"] >= ranked[1]["wlc_score"] >= ranked[2]["wlc_score"]


def test_top_suppliers_sorts_before_slice() -> None:
    messy = [
        {"id": 1, "wlc_score": 0.5, "extended_total_pen": 100, "bottleneck_lead_days": 1},
        {"id": 2, "wlc_score": 0.9, "extended_total_pen": 200, "bottleneck_lead_days": 2},
        {"id": 3, "wlc_score": 0.7, "extended_total_pen": 150, "bottleneck_lead_days": 1},
    ]
    top2 = top_suppliers(messy, 2)
    assert [t["id"] for t in top2] == [2, 3]


def test_score_supplier_quotes_empty() -> None:
    assert score_supplier_quotes([]) == []


def test_rank_fast_delivery_when_pool_max_lead_is_three() -> None:
    fast = _quote(10, "Fast", "30000", 1, "8.0")
    slow = _quote(11, "Slow", "25000", 3, "9.0")
    ranked = score_supplier_quotes([fast, slow])
    assert ranked[0]["id"] == 10
