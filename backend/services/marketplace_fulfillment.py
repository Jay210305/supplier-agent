"""Marketplace-only fulfillment helpers (virtual supplier IDs, DB placeholder)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.supplier import Supplier

_PLACEHOLDER_COMPANY = "Catálogo externo (marketplace)"
from schemas.catalog_source import MarketplaceListing
from schemas.procurement_request import ProcurementItem, ProcurementRequestExtracted
from services.scoring import SupplierQuote

logger = logging.getLogger(__name__)

# Seeded in db/seed.py — FK target when the winning quote is a marketplace source.
MARKETPLACE_PLACEHOLDER_RUC = "20999999990"


@dataclass(frozen=True)
class SupplierPDFView:
    """Supplier fields consumed by the PO PDF renderer."""

    company_name: str
    ruc: str
    email: str | None


def is_virtual_supplier_id(supplier_id: int) -> bool:
    return int(supplier_id) < 0


def virtual_catalog_source_id(supplier_id: int) -> int:
    return abs(int(supplier_id))


async def get_marketplace_placeholder_supplier(session: AsyncSession) -> Supplier:
    result = await session.execute(
        select(Supplier).where(Supplier.ruc == MARKETPLACE_PLACEHOLDER_RUC).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = Supplier(
        company_name=_PLACEHOLDER_COMPANY,
        ruc=MARKETPLACE_PLACEHOLDER_RUC,
        email="marketplace@catalog.local",
        rating=Decimal("7.00"),
        is_active=True,
    )
    session.add(row)
    await session.flush()
    logger.info("Created marketplace placeholder supplier id=%s", row.id)
    return row


def supplier_pdf_view(
    supplier: Supplier, *, chosen: dict, virtual_supplier_id: int | None
) -> SupplierPDFView:
    if virtual_supplier_id is not None and is_virtual_supplier_id(virtual_supplier_id):
        return SupplierPDFView(
            company_name=str(chosen.get("name") or supplier.company_name),
            ruc=MARKETPLACE_PLACEHOLDER_RUC,
            email=str(chosen.get("email") or supplier.email),
        )
    return SupplierPDFView(
        company_name=supplier.company_name,
        ruc=supplier.ruc,
        email=supplier.email,
    )


def _norm_query(value: str) -> str:
    return " ".join(value.lower().split())


def _budget_applies(quote_currency: str, line_currencies: set[str], budget_currency: str) -> bool:
    """Only enforce max_budget when totals are in the request currency."""
    if quote_currency.upper() != budget_currency.upper():
        return False
    return all(c.upper() == budget_currency.upper() for c in line_currencies)


def build_quotes_from_market_snapshot(
    snapshot: list[MarketplaceListing],
    request: ProcurementRequestExtracted,
    *,
    days_available: int | None,
) -> list[SupplierQuote]:
    """Build virtual supplier quotes from parse-time snapshot (no strict title match)."""
    by_source: dict[int, list[MarketplaceListing]] = {}
    for row in snapshot:
        by_source.setdefault(row.source_id, []).append(row)

    quotes: list[SupplierQuote] = []
    budget = request.constraints.currency

    for source_id, rows in by_source.items():
        line_picks: list[dict] = []
        extended = Decimal("0")
        max_lead = 0
        adapter_key = "scraperapi"
        rating = Decimal("7.00")
        source_name = rows[0].source_name
        line_currencies: set[str] = set()

        for item in request.items:
            pick = _pick_listing_for_item(item, rows)
            if pick is None:
                break
            line_ext = pick.unit_price * item.quantity
            extended += line_ext
            max_lead = max(max_lead, pick.lead_time_days)
            adapter_key = pick.adapter_key
            line_currencies.add(pick.currency.upper())
            line_picks.append(
                {
                    "product_id": None,
                    "external_source_id": source_id,
                    "product_name": pick.product_name,
                    "sku": None,
                    "url": pick.url,
                    "quantity": item.quantity,
                    "unit_price": str(pick.unit_price),
                    "line_total": str(line_ext),
                    "lead_time_days": pick.lead_time_days,
                    "currency": pick.currency,
                }
            )
        else:
            if _budget_applies(budget, line_currencies, budget) and extended > request.constraints.max_budget:
                logger.debug(
                    "Snapshot source %s skipped: %s %s > budget %s",
                    source_name,
                    extended,
                    budget,
                    request.constraints.max_budget,
                )
                continue
            if days_available is not None and max_lead > days_available:
                continue
            quotes.append(
                SupplierQuote(
                    supplier_id=-abs(source_id),
                    company_name=f"[{adapter_key}] {source_name}",
                    ruc="00000000000",
                    email=f"external+{source_id}@catalog.local",
                    rating=rating,
                    extended_total=extended,
                    bottleneck_lead_days=max_lead,
                    lines=tuple(line_picks),
                )
            )
    return quotes


def _pick_listing_for_item(
    item: ProcurementItem, rows: list[MarketplaceListing]
) -> MarketplaceListing | None:
    needle = _norm_query(item.product)
    scoped = [r for r in rows if _norm_query(r.query) == needle]
    if not scoped:
        scoped = rows
    if not scoped:
        return None
    return min(scoped, key=lambda r: (r.unit_price, r.lead_time_days))
