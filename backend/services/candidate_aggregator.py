"""Merge local DB suppliers and external catalog sources into one quote pool.

Local suppliers are still produced by `services.procurement_candidates`
(unchanged). External sources are queried via `services.catalog_search` and
turned into transient `SupplierQuote` rows — one quote per external source per
request — using a virtual `supplier_id = -<catalog_source_id>` so the scoring
layer can keep treating quotes uniformly without colliding with real IDs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.catalog_source import ExternalProductResult
from schemas.procurement_request import ProcurementItem, ProcurementRequestExtracted
from services.catalog_search import search_many_queries
from services.procurement_candidates import (
    build_supplier_quotes,
    product_matches_item,
)
from services.scoring import SupplierQuote

logger = logging.getLogger(__name__)


def _virtual_supplier_id(catalog_source_id: int) -> int:
    """Map a CatalogSource.id → negative integer so it never collides with suppliers.id."""
    return -abs(int(catalog_source_id))


def _pick_best_external_for_item(
    item: ProcurementItem, results: list[ExternalProductResult]
) -> ExternalProductResult | None:
    candidates = [
        r
        for r in results
        if product_matches_item(item.product, r.product_name, r.description)
        and r.available_stock >= item.quantity
        and r.minimum_order_quantity <= item.quantity
    ]
    if not candidates:
        return None
    return min(
        candidates, key=lambda r: (r.unit_price * item.quantity, r.lead_time_days)
    )


def _external_results_to_quote(
    source_id: int,
    source_name: str,
    per_query: dict[str, list[ExternalProductResult]],
    request: ProcurementRequestExtracted,
    days_available: int | None,
) -> SupplierQuote | None:
    """Build one `SupplierQuote` covering ALL request lines from one external source.

    Returns `None` if the source can't cover every line within constraints —
    same all-or-nothing logic as the local matcher.
    """
    line_picks: list[dict] = []
    extended = Decimal("0")
    max_lead = 0
    adapter_key = "external"
    rating = Decimal("5.00")
    currency = request.constraints.currency

    for item in request.items:
        hits = per_query.get(item.product, [])
        pick = _pick_best_external_for_item(item, hits)
        if pick is None:
            return None
        line_ext = pick.unit_price * item.quantity
        extended += line_ext
        max_lead = max(max_lead, pick.lead_time_days)
        rating = pick.rating
        adapter_key = pick.adapter_key
        line_picks.append(
            {
                "product_id": None,
                "external_source_id": source_id,
                "product_name": pick.product_name,
                "sku": pick.sku,
                "url": pick.url,
                "quantity": item.quantity,
                "unit_price": str(pick.unit_price),
                "line_total": str(line_ext),
                "lead_time_days": pick.lead_time_days,
                "currency": pick.currency,
            }
        )

    if extended > request.constraints.max_budget:
        logger.debug(
            "External source %s skipped: extended %s > budget %s",
            source_name,
            extended,
            request.constraints.max_budget,
        )
        return None
    if days_available is not None and max_lead > days_available:
        logger.debug(
            "External source %s skipped: max_lead %s > days_available %s",
            source_name,
            max_lead,
            days_available,
        )
        return None

    return SupplierQuote(
        supplier_id=_virtual_supplier_id(source_id),
        company_name=f"[{adapter_key}] {source_name}",
        ruc="00000000000",
        email=f"external+{source_id}@catalog.local",
        rating=rating,
        extended_total=extended,
        bottleneck_lead_days=max_lead,
        lines=tuple(line_picks),
    )


async def aggregate_supplier_quotes(
    session: AsyncSession,
    request: ProcurementRequestExtracted,
    *,
    include_external: bool = True,
    source_ids: list[int] | None = None,
) -> list[SupplierQuote]:
    """Local DB pool + external catalog pool, ready for `score_supplier_quotes`."""
    local_quotes = await build_supplier_quotes(session, request)

    if not include_external:
        return local_quotes

    queries = [item.product for item in request.items]
    per_source: dict[int, dict[str, list[ExternalProductResult]]] = (
        await search_many_queries(session, queries, source_ids=source_ids)
    )

    today = datetime.now(timezone.utc).date()
    deadline = request.constraints.delivery_before
    days_available = (deadline - today).days if deadline is not None else None

    external_quotes: list[SupplierQuote] = []
    for source_id, per_query in per_source.items():
        # Source name is taken from the first hit if any; fall back to id otherwise
        any_hit: ExternalProductResult | None = next(
            (h for hits in per_query.values() for h in hits), None
        )
        source_name = any_hit.source_name if any_hit else f"source#{source_id}"
        quote = _external_results_to_quote(
            source_id=source_id,
            source_name=source_name,
            per_query=per_query,
            request=request,
            days_available=days_available,
        )
        if quote is not None:
            external_quotes.append(quote)

    merged = local_quotes + external_quotes
    logger.info(
        "Aggregated %s quotes (local=%s, external=%s) for request %s",
        len(merged),
        len(local_quotes),
        len(external_quotes),
        request.request_id,
    )
    return merged
