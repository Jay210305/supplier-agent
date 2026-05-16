"""
Weighted Linear Combination (WLC) supplier scoring (AGENTS.md §11).
supplier_price = extended line total (Σ unit_price × quantity) for the request.
Pool maxima: max extended total and max bottleneck lead time among eligible suppliers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

WEIGHT_PRICE = 0.4
WEIGHT_DELIVERY = 0.4
WEIGHT_RELIABILITY = 0.2


class ScoringError(Exception):
    """Invalid input or empty pool for scoring."""


@dataclass(frozen=True)
class SupplierQuote:
    """One supplier's fulfillment plan for the whole procurement request."""

    supplier_id: int
    company_name: str
    ruc: str
    email: str
    rating: Decimal
    extended_total: Decimal
    bottleneck_lead_days: int
    lines: tuple[dict[str, Any], ...]


def wlc_components(
    extended_total: Decimal,
    bottleneck_lead_days: int,
    reliability_rating: float,
    max_price: Decimal,
    max_lead_time: int,
) -> tuple[float, float, float, float]:
    """Returns (price_score, delivery_score, reliability_score, wlc_score)."""
    if max_price <= 0:
        price_score = 0.0
    else:
        price_score = float(1 - min(extended_total / max_price, Decimal("1")))

    if max_lead_time <= 0:
        delivery_score = 0.0 if bottleneck_lead_days > 0 else 1.0
    else:
        delivery_score = 1.0 - min(bottleneck_lead_days / max_lead_time, 1.0)

    reliability_score = max(0.0, min(1.0, reliability_rating / 10.0))
    price_score = max(0.0, min(1.0, price_score))
    delivery_score = max(0.0, min(1.0, delivery_score))

    wlc = (
        WEIGHT_PRICE * price_score
        + WEIGHT_DELIVERY * delivery_score
        + WEIGHT_RELIABILITY * reliability_score
    )
    return price_score, delivery_score, reliability_score, wlc


def score_supplier_quotes(quotes: list[SupplierQuote]) -> list[dict[str, Any]]:
    """
    Rank suppliers by WLC. Tie-break: higher WLC, lower extended total, lower lead, higher id.
    """
    if not quotes:
        return []

    max_price = max(q.extended_total for q in quotes)
    max_lead = max(q.bottleneck_lead_days for q in quotes)

    scored: list[dict[str, Any]] = []
    for q in quotes:
        ps, ds, rs, wlc = wlc_components(
            q.extended_total,
            q.bottleneck_lead_days,
            float(q.rating),
            max_price,
            max_lead,
        )
        scored.append(
            {
                "id": q.supplier_id,
                "name": q.company_name,
                "ruc": q.ruc,
                "email": q.email,
                "rating": float(q.rating),
                "extended_total_pen": float(q.extended_total),
                "bottleneck_lead_days": q.bottleneck_lead_days,
                "lines": [dict(line) for line in q.lines],
                "price_score": ps,
                "delivery_score": ds,
                "reliability_score": rs,
                "wlc_score": wlc,
            }
        )

    scored.sort(
        key=lambda r: (
            -r["wlc_score"],
            r["extended_total_pen"],
            r["bottleneck_lead_days"],
            -r["id"],
        )
    )
    logger.debug("WLC ranked %s suppliers", len(scored))
    return scored


def top_suppliers(scored: list[dict[str, Any]], count: int = 3) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    ranked = sorted(
        scored,
        key=lambda r: (
            -float(r.get("wlc_score", 0)),
            float(r.get("extended_total_pen", 0)),
            int(r.get("bottleneck_lead_days", 0)),
            -int(r.get("id", 0)),
        ),
    )
    return ranked[: min(count, len(ranked))]
