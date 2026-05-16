"""Match procurement items to catalog products and build supplier quotes."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.product import Product
from models.supplier import Supplier
from schemas.procurement_request import ProcurementItem, ProcurementRequestExtracted
from services.scoring import SupplierQuote

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


def product_matches_item(item_product: str, product_name: str, description: str | None) -> bool:
    needle = _normalize(item_product)
    hay = _normalize(f"{product_name} {(description or '')}")
    if not needle:
        return False
    for token in needle.split():
        if len(token) < 2:
            continue
        if token not in hay:
            return False
    return True


def _best_product_for_line(
    products: Sequence[Product], item: ProcurementItem
) -> Product | None:
    candidates = [
        p
        for p in products
        if product_matches_item(item.product, p.name, p.description)
        and p.available_stock >= item.quantity
        and p.minimum_order_quantity <= item.quantity
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: (p.unit_price * item.quantity, p.lead_time_days, p.id))


async def estimate_minimum_order_total(
    session: AsyncSession, items: list[ProcurementItem]
) -> Decimal | None:
    """Cheapest catalog cost per line summed (lower bound; lines may come from different suppliers)."""
    stmt = (
        select(Product)
        .options(selectinload(Product.supplier))
        .join(Supplier)
        .where(Product.is_active.is_(True), Supplier.is_active.is_(True))
    )
    result = await session.execute(stmt)
    all_products = result.scalars().unique().all()

    total = Decimal("0")
    for item in items:
        best: Product | None = None
        best_ext: Decimal | None = None
        for p in all_products:
            if not product_matches_item(item.product, p.name, p.description):
                continue
            if p.available_stock < item.quantity or p.minimum_order_quantity > item.quantity:
                continue
            ext = p.unit_price * item.quantity
            if best is None or ext < best_ext:  # type: ignore[operator]
                best = p
                best_ext = ext
        if best is None or best_ext is None:
            return None
        total += best_ext
    return total


async def build_supplier_quotes(
    session: AsyncSession,
    request: ProcurementRequestExtracted,
) -> list[SupplierQuote]:
    stmt = (
        select(Supplier)
        .options(selectinload(Supplier.products))
        .where(Supplier.is_active.is_(True))
    )
    result = await session.execute(stmt)
    suppliers = result.scalars().unique().all()

    quotes: list[SupplierQuote] = []
    budget = request.constraints.max_budget
    delivery_before = request.constraints.delivery_before
    today = datetime.now(timezone.utc).date()
    deadline = delivery_before

    days_available: int | None = None
    if deadline is not None:
        days_available = (deadline - today).days

    for sup in suppliers:
        products = [p for p in sup.products if p.is_active]
        line_picks: list[dict] = []
        extended = Decimal("0")
        max_lead = 0
        ok = True
        for item in request.items:
            pick = _best_product_for_line(products, item)
            if pick is None:
                ok = False
                break
            line_ext = pick.unit_price * item.quantity
            extended += line_ext
            max_lead = max(max_lead, pick.lead_time_days)
            line_picks.append(
                {
                    "product_id": pick.id,
                    "product_name": pick.name,
                    "sku": pick.sku,
                    "quantity": item.quantity,
                    "unit_price": str(pick.unit_price),
                    "line_total": str(line_ext),
                    "lead_time_days": pick.lead_time_days,
                }
            )

        if not ok:
            continue
        if extended > budget:
            continue
        if days_available is not None and max_lead > days_available:
            continue

        quotes.append(
            SupplierQuote(
                supplier_id=sup.id,
                company_name=sup.company_name,
                ruc=sup.ruc,
                email=sup.email,
                rating=sup.rating,
                extended_total=extended,
                bottleneck_lead_days=max_lead,
                lines=tuple(line_picks),
            )
        )

    logger.info("Built %s supplier quotes for request %s", len(quotes), request.request_id)
    return quotes
