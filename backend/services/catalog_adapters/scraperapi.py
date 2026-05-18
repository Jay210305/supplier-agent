"""ScraperAPI-backed HTML scraping adapter.

Same selector model as :class:`GenericHttpAdapter`, but the HTTP GET goes
through ScraperAPI's proxy endpoint (``http://api.scraperapi.com/``), which
handles rotating IPs, CAPTCHAs and—when ``config.render`` is true—headless
JavaScript rendering for sites that hydrate prices client-side.

Configure via ``CatalogSource.config`` (all `generic_http` fields apply, plus):

    {
      "search_url_template": "https://www.example.com/search?q={query}",
      "item_selector": "li.product",
      "name_selector": "h2.title",
      "price_selector": "span.price",
      "render": true,                # JS rendering (extra cost/latency)
      "country_code": "us",          # 2-letter ISO geo proxy
      "premium": false,              # premium residential pool
      "ultra_premium": false,        # advanced bypass (mutually exclusive with premium)
      "device_type": "desktop"      # "desktop" | "mobile"
    }

Authentication: ``CatalogSource.auth = {"api_key": "..."}`` (preferred) or the
``SCRAPERAPI_API_KEY`` env var, merged via ``catalog_search._merged_auth``.
"""

from __future__ import annotations

import asyncio
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
    SourceContext,
)
from services.catalog_adapters.generic_http import GenericHttpAdapter

logger = logging.getLogger(__name__)

SCRAPERAPI_ENDPOINT = "http://api.scraperapi.com/"

_BOOL_FLAGS = ("render", "premium", "ultra_premium")
_STR_FLAGS = ("country_code", "device_type")


class ScraperApiAdapter(GenericHttpAdapter):
    """Proxy fetch through ScraperAPI, parse with the generic selector pipeline."""

    metadata = AdapterMetadata(
        key="scraperapi",
        kind=CatalogSourceKind.WEBSITE,
        description=(
            "HTML scraping via ScraperAPI proxy (bot bypass, geo, optional JS render). "
            "Same selector config as generic_http plus ScraperAPI flags."
        ),
        requires_auth=True,
        auth_fields=("api_key",),
        config_fields=(
            "search_url_template",
            "item_selector",
            "name_selector",
            "price_selector",
            "url_selector",
            "url_attribute",
            "image_selector",
            "image_attribute",
            "currency",
            "price_regex",
            "render",
            "country_code",
            "premium",
            "ultra_premium",
            "device_type",
            "query_format",
        ),
    )

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        results = await super().search(query, limit, ctx)
        if results or not _truthy((ctx.config or {}).get("render")):
            return results
        # JS-rendered SERPs often return a skeleton on the first ScraperAPI pass.
        await asyncio.sleep(3)
        return await super().search(query, limit, ctx)

    async def _fetch_search_document(
        self, target_url: str, ctx: SourceContext
    ) -> tuple[str, str]:
        api_key = (ctx.auth or {}).get("api_key")
        if not api_key:
            raise AdapterAuthError(
                f"{ctx.source.name}: ScraperAPI api_key missing "
                "(set CatalogSource.auth.api_key or SCRAPERAPI_API_KEY)."
            )

        params: dict[str, str] = {"api_key": str(api_key), "url": target_url}
        cfg = ctx.config or {}
        for flag in _BOOL_FLAGS:
            if _truthy(cfg.get(flag)):
                params[flag] = "true"
        for flag in _STR_FLAGS:
            value = cfg.get(flag)
            if value:
                params[flag] = str(value)

        if params.get("premium") == "true" and params.get("ultra_premium") == "true":
            raise AdapterError(
                f"{ctx.source.name}: 'premium' and 'ultra_premium' are mutually exclusive."
            )

        try:
            response = await ctx.client.get(
                SCRAPERAPI_ENDPOINT, params=params, follow_redirects=True
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise AdapterTimeoutError(f"{ctx.source.name} ScraperAPI timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AdapterError(
                f"{ctx.source.name} ScraperAPI HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise AdapterError(f"{ctx.source.name} ScraperAPI request error: {e}") from e

        # Relative links in the scraped page resolve against the *target* URL,
        # not the proxy endpoint.
        return response.text, target_url


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)
