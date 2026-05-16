"""MercadoLibre public Search API adapter.

Uses the unauthenticated `/sites/{site_id}/search` endpoint. Default site is
`MPE` (Perú). Works out of the box; useful as the default-enabled source so
the procurement pipeline can demo internet search without any credentials.

Docs: https://developers.mercadolibre.com.pe/en_us/items-and-searches
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from models.enums import CatalogSourceKind
from schemas.catalog_source import ExternalProductResult
from services.catalog_adapters.base import (
    AdapterError,
    AdapterMetadata,
    AdapterTimeoutError,
    CatalogAdapter,
    SourceContext,
    _safe_decimal,
)

logger = logging.getLogger(__name__)


_LEAD_TIME_DEFAULT = 7
_LEAD_TIME_FULL = 2  # MELI "FULL" / "fulfillment" ships from MELI warehouse


class MercadoLibreAdapter(CatalogAdapter):
    metadata = AdapterMetadata(
        key="mercadolibre",
        kind=CatalogSourceKind.WEBSITE,
        description="MercadoLibre public Search API (no auth required).",
        requires_auth=False,
        config_fields=("site_id",),
    )

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        site_id: str = (ctx.config.get("site_id") or "MPE").upper()
        base = (ctx.source.endpoint or "https://api.mercadolibre.com").rstrip("/")
        url = f"{base}/sites/{site_id}/search"
        params = {"q": query, "limit": min(max(limit, 1), 50)}

        try:
            response = await ctx.client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise AdapterTimeoutError(f"MercadoLibre timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AdapterError(
                f"MercadoLibre HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        except httpx.RequestError as e:
            raise AdapterError(f"MercadoLibre request error: {e}") from e

        try:
            body = response.json()
        except ValueError as e:
            raise AdapterError(f"MercadoLibre invalid JSON: {e}") from e

        items: list[dict[str, Any]] = body.get("results") or []
        out: list[ExternalProductResult] = []
        for item in items[:limit]:
            try:
                out.append(self._normalize(item, ctx))
            except Exception as exc:
                logger.debug("MercadoLibre item rejected (%s): %s", exc, item.get("id"))
                continue
        return out

    @staticmethod
    def _normalize(item: dict[str, Any], ctx: SourceContext) -> ExternalProductResult:
        price = _safe_decimal(item.get("price"))
        currency = (item.get("currency_id") or ctx.source.currency or "PEN").upper()

        shipping = item.get("shipping") or {}
        logistic_type = (shipping.get("logistic_type") or "").lower()
        lead_time = _LEAD_TIME_FULL if logistic_type == "fulfillment" else _LEAD_TIME_DEFAULT

        stock = int(item.get("available_quantity") or 0) or 9999

        return ExternalProductResult(
            source_id=ctx.source.id,
            source_name=ctx.source.name,
            adapter_key=ctx.source.adapter_key,
            product_name=str(item.get("title") or "")[:512] or "(sin título)",
            description=None,
            sku=str(item.get("id") or "")[:128] or None,
            url=item.get("permalink"),
            image_url=item.get("thumbnail"),
            unit_price=price,
            currency=currency[:3],
            lead_time_days=lead_time,
            available_stock=stock,
            minimum_order_quantity=1,
            rating=ctx.source.reliability_rating,
            raw={
                "id": item.get("id"),
                "condition": item.get("condition"),
                "seller_id": (item.get("seller") or {}).get("id"),
                "logistic_type": logistic_type,
            },
        )
