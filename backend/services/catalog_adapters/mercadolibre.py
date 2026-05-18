"""MercadoLibre catalog search adapter.

MercadoLibre discontinued public `/sites/{site_id}/search?q=` (403 even with OAuth).
This adapter uses `/products/search` and enriches each hit via `/products/{id}`
(`buy_box_winner` or `buy_box_winner_price_range.min`).

Docs: https://developers.mercadolibre.com.ar/en_us/list-products/products-search
Auth on `CatalogSource.auth` or `.env` (`MELI_*`):
  - `access_token` (required)
  - optional `refresh_token`, `client_id`, `client_secret` for auto-refresh
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


_LEAD_TIME_DEFAULT = 7
_LEAD_TIME_FULL = 2

_MISSING_TOKEN_HINT = (
    "MercadoLibre requiere OAuth. Crea una app en https://developers.mercadolibre.com.pe, "
    "autorízala y configura `access_token` en la fuente o `MELI_ACCESS_TOKEN` en .env."
)

_SEARCH_DENIED_HINT = (
    "MercadoLibre rechazó la búsqueda de catálogo (HTTP 403) con el token actual. "
    "Reautoriza la app con los scopes de lectura/catálogo o verifica que la app esté activa."
)

_NO_PRICED_RESULTS_HINT = (
    "MercadoLibre devolvió productos de catálogo sin precio (sin buy_box_winner ni rango). "
    "Puede que no haya publicaciones competiendo en este sitio para la consulta, o que la app "
    "OAuth no tenga permisos de catálogo/marketplace."
)


def _token_from_auth(auth: dict[str, Any]) -> str | None:
    for key in ("access_token", "oauth_token"):
        value = auth.get(key)
        if value:
            return str(value).strip()
    return None


class MercadoLibreAdapter(CatalogAdapter):
    metadata = AdapterMetadata(
        key="mercadolibre",
        kind=CatalogSourceKind.WEBSITE,
        description="MercadoLibre catalog search API (OAuth; uses /products/search).",
        requires_auth=True,
        auth_fields=("access_token", "refresh_token", "client_id", "client_secret"),
        config_fields=("site_id",),
    )

    async def _resolve_token(self, ctx: SourceContext) -> str:
        token = _token_from_auth(ctx.auth)
        if token:
            return token
        raise AdapterAuthError(_MISSING_TOKEN_HINT)

    async def _refresh_token(self, ctx: SourceContext) -> str | None:
        refresh = (ctx.auth.get("refresh_token") or "").strip()
        client_id = (ctx.auth.get("client_id") or "").strip()
        client_secret = (ctx.auth.get("client_secret") or "").strip()
        if not (refresh and client_id and client_secret):
            return None

        base = (ctx.source.endpoint or "https://api.mercadolibre.com").rstrip("/")
        try:
            response = await ctx.client.post(
                f"{base}/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            logger.warning("MercadoLibre token refresh failed: %s", exc)
            return None

        new_token = (body.get("access_token") or "").strip()
        if new_token:
            ctx.auth["access_token"] = new_token
            if body.get("refresh_token"):
                ctx.auth["refresh_token"] = body["refresh_token"]
        return new_token or None

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        site_id: str = (ctx.config.get("site_id") or "MPE").upper()
        base = (ctx.source.endpoint or "https://api.mercadolibre.com").rstrip("/")
        effective_limit = min(max(limit, 1), 50)

        token = await self._resolve_token(ctx)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            return await self._search_catalog(
                base, site_id, query, effective_limit, ctx, headers
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                refreshed = await self._refresh_token(ctx)
                if refreshed:
                    headers["Authorization"] = f"Bearer {refreshed}"
                    return await self._search_catalog(
                        base, site_id, query, effective_limit, ctx, headers
                    )
                raise self._http_error(e, token_present=True) from e
            raise AdapterError(
                f"MercadoLibre HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        except httpx.TimeoutException as e:
            raise AdapterTimeoutError(f"MercadoLibre timeout: {e}") from e
        except httpx.RequestError as e:
            raise AdapterError(f"MercadoLibre request error: {e}") from e

    async def _search_catalog(
        self,
        base: str,
        site_id: str,
        query: str,
        limit: int,
        ctx: SourceContext,
        headers: dict[str, str],
    ) -> list[ExternalProductResult]:
        response = await ctx.client.get(
            f"{base}/products/search",
            params={
                "site_id": site_id,
                "status": "active",
                "q": query,
                "limit": min(limit * 3, 50),
            },
            headers=headers,
        )
        response.raise_for_status()

        try:
            body = response.json()
        except ValueError as e:
            raise AdapterError(f"MercadoLibre invalid JSON: {e}") from e

        catalog_hits: list[dict[str, Any]] = body.get("results") or []
        out: list[ExternalProductResult] = []

        for hit in catalog_hits:
            if len(out) >= limit:
                break
            product_id = str(hit.get("id") or hit.get("catalog_product_id") or "").strip()
            if not product_id:
                continue
            try:
                detail = await self._fetch_product(base, product_id, headers, ctx)
            except httpx.HTTPStatusError as exc:
                logger.debug("MercadoLibre product %s skipped: %s", product_id, exc)
                continue
            except httpx.RequestError as exc:
                logger.debug("MercadoLibre product %s request failed: %s", product_id, exc)
                continue

            merged = {**hit, **detail}
            priced = self._normalize_catalog_product(merged, ctx)
            if priced is not None:
                out.append(priced)

        if catalog_hits and not out:
            raise AdapterError(_NO_PRICED_RESULTS_HINT)
        return out

    async def _fetch_product(
        self,
        base: str,
        product_id: str,
        headers: dict[str, str],
        ctx: SourceContext,
    ) -> dict[str, Any]:
        response = await ctx.client.get(f"{base}/products/{product_id}", headers=headers)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise AdapterError(f"MercadoLibre product {product_id}: unexpected payload")
        return body

    @staticmethod
    def _http_error(error: httpx.HTTPStatusError, *, token_present: bool) -> AdapterError:
        text = (error.response.text or "")[:300]
        if error.response.status_code == 401:
            return AdapterAuthError(
                f"Token de MercadoLibre inválido o expirado. {_MISSING_TOKEN_HINT} ({text})"
            )
        if token_present and error.response.status_code == 403:
            return AdapterError(f"{_SEARCH_DENIED_HINT} ({text})")
        return AdapterAuthError(
            f"MercadoLibre auth failed (HTTP {error.response.status_code}): {text}"
        )

    @staticmethod
    def _price_from_range(price_range: dict[str, Any] | None) -> tuple[Any, str | None]:
        if not price_range:
            return None, None
        minimum = price_range.get("min") or {}
        price = minimum.get("price")
        currency = minimum.get("currency_id")
        return price, currency

    def _normalize_catalog_product(
        self, product: dict[str, Any], ctx: SourceContext
    ) -> ExternalProductResult | None:
        buy_box = product.get("buy_box_winner") or {}
        price = buy_box.get("price")
        currency = buy_box.get("currency_id")

        if price is None:
            price, range_currency = self._price_from_range(
                product.get("buy_box_winner_price_range")
            )
            currency = currency or range_currency

        if price is None or price == "":
            return None
        unit_price = _safe_decimal(price)
        if unit_price <= 0:
            return None

        currency = (currency or ctx.source.currency or "PEN").upper()
        name = (
            str(product.get("name") or product.get("family_name") or "").strip()[:512]
            or "(sin título)"
        )

        shipping = buy_box.get("shipping") or {}
        logistic_type = (shipping.get("logistic_type") or "").lower()
        lead_time = _LEAD_TIME_FULL if logistic_type == "fulfillment" else _LEAD_TIME_DEFAULT

        stock = int(buy_box.get("available_quantity") or 0) or 9999
        item_id = buy_box.get("item_id")
        sku = str(item_id or product.get("id") or "")[:128] or None
        permalink = (product.get("permalink") or buy_box.get("permalink") or "").strip() or None

        pictures = product.get("pictures") or []
        image_url = None
        if pictures and isinstance(pictures[0], dict):
            image_url = pictures[0].get("url") or pictures[0].get("secure_url")

        return ExternalProductResult(
            source_id=ctx.source.id,
            source_name=ctx.source.name,
            adapter_key=ctx.source.adapter_key,
            product_name=name,
            description=None,
            sku=sku,
            url=permalink,
            image_url=image_url,
            unit_price=unit_price,
            currency=currency[:3],
            lead_time_days=lead_time,
            available_stock=stock,
            minimum_order_quantity=1,
            rating=ctx.source.reliability_rating,
            raw={
                "catalog_product_id": product.get("id"),
                "item_id": item_id,
                "condition": buy_box.get("condition"),
                "seller_id": buy_box.get("seller_id"),
                "logistic_type": logistic_type,
            },
        )
