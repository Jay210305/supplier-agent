"""eBay Browse API adapter — requires an OAuth bearer token.

Docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
Auth: store `{"oauth_token": "..."}` on `CatalogSource.auth`. Optional
`config = {"marketplace_id": "EBAY_US"}` overrides the default marketplace.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from models.enums import CatalogSourceKind
from schemas.catalog_source import ExternalProductResult
from services.catalog_adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterMetadata,
    AdapterTimeoutError,
    CatalogAdapter,
    SourceContext,
    _safe_decimal,
)

logger = logging.getLogger(__name__)


class EbayAdapter(CatalogAdapter):
    metadata = AdapterMetadata(
        key="ebay",
        kind=CatalogSourceKind.WEBSITE,
        description="eBay Browse API (OAuth bearer token required).",
        requires_auth=True,
        auth_fields=("oauth_token",),
        config_fields=("marketplace_id",),
    )

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        token = ctx.auth.get("oauth_token")
        if not token:
            raise AdapterAuthError("eBay OAuth token missing on CatalogSource.auth.oauth_token")

        base = (ctx.source.endpoint or "https://api.ebay.com").rstrip("/")
        url = f"{base}/buy/browse/v1/item_summary/search"
        marketplace = ctx.config.get("marketplace_id") or "EBAY_US"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": marketplace,
            "Content-Type": "application/json",
        }
        params = {"q": query, "limit": min(max(limit, 1), 50)}

        try:
            response = await ctx.client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise AdapterTimeoutError(f"eBay timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise AdapterAuthError(f"eBay auth failed: {e.response.status_code}") from e
            raise AdapterError(
                f"eBay HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        except httpx.RequestError as e:
            raise AdapterError(f"eBay request error: {e}") from e

        try:
            body = response.json()
        except ValueError as e:
            raise AdapterError(f"eBay invalid JSON: {e}") from e

        items: list[dict[str, Any]] = body.get("itemSummaries") or []
        out: list[ExternalProductResult] = []
        for item in items[:limit]:
            try:
                out.append(self._normalize(item, ctx))
            except Exception as exc:
                logger.debug("eBay item rejected (%s): %s", exc, item.get("itemId"))
                continue
        return out

    @staticmethod
    def _normalize(item: dict[str, Any], ctx: SourceContext) -> ExternalProductResult:
        price_info = item.get("price") or {}
        price = _safe_decimal(price_info.get("value"))
        currency = (price_info.get("currency") or ctx.source.currency or "USD").upper()
        images = item.get("image") or {}

        return ExternalProductResult(
            source_id=ctx.source.id,
            source_name=ctx.source.name,
            adapter_key=ctx.source.adapter_key,
            product_name=str(item.get("title") or "")[:512] or "(no title)",
            description=item.get("shortDescription"),
            sku=str(item.get("itemId") or "")[:128] or None,
            url=item.get("itemWebUrl"),
            image_url=images.get("imageUrl"),
            unit_price=price,
            currency=currency[:3],
            lead_time_days=7,
            available_stock=9999,
            minimum_order_quantity=1,
            rating=ctx.source.reliability_rating,
            raw={
                "itemId": item.get("itemId"),
                "condition": item.get("condition"),
                "buyingOptions": item.get("buyingOptions"),
            },
        )
