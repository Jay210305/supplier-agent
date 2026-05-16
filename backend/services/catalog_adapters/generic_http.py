"""Generic HTML-scraping adapter driven by CSS selectors.

Configure via `CatalogSource.config`:
  {
    "search_url_template": "https://www.example.com/search?q={query}",
    "item_selector": "li.product",
    "name_selector": "h2.title",
    "price_selector": "span.price",
    "url_selector": "a.product-link",                # optional
    "url_attribute": "href",                          # optional, default "href"
    "image_selector": "img",                          # optional
    "image_attribute": "src",                         # optional, default "src"
    "currency": "PEN",                                # optional override
    "price_regex": "\\d+(?:[\\.,]\\d+)?"             # optional, default extracts first number
  }
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser, Node

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

_DEFAULT_PRICE_RE = re.compile(r"(\d+(?:[\.,]\d{1,2})?)")
_USER_AGENT = (
    "Mozilla/5.0 (compatible; SupplierAgent/0.1; +https://github.com/yourorg/supplier-agent)"
)


class GenericHttpAdapter(CatalogAdapter):
    metadata = AdapterMetadata(
        key="generic_http",
        kind=CatalogSourceKind.WEBSITE,
        description="HTML-scraping adapter configured with CSS selectors per source.",
        requires_auth=False,
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
        ),
    )

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        cfg = ctx.config or {}
        template = cfg.get("search_url_template")
        item_sel = cfg.get("item_selector")
        name_sel = cfg.get("name_selector")
        price_sel = cfg.get("price_selector")
        if not template or not item_sel or not name_sel or not price_sel:
            raise AdapterError(
                "GenericHttpAdapter requires search_url_template, "
                "item_selector, name_selector and price_selector in config."
            )

        url = template.format(query=httpx.QueryParams({"q": query})["q"])
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "es-PE,es;q=0.9,en;q=0.8"}

        try:
            response = await ctx.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise AdapterTimeoutError(f"{ctx.source.name} timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AdapterError(
                f"{ctx.source.name} HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise AdapterError(f"{ctx.source.name} request error: {e}") from e

        html = response.text
        tree = HTMLParser(html)
        nodes = tree.css(item_sel)
        if not nodes:
            return []

        price_re = re.compile(cfg.get("price_regex") or _DEFAULT_PRICE_RE.pattern)
        currency = (cfg.get("currency") or ctx.source.currency or "PEN").upper()[:3]
        url_attr = cfg.get("url_attribute") or "href"
        img_attr = cfg.get("image_attribute") or "src"

        results: list[ExternalProductResult] = []
        for node in nodes[: max(limit, 1)]:
            try:
                result = self._normalize(
                    node=node,
                    base_url=str(response.url),
                    name_selector=name_sel,
                    price_selector=price_sel,
                    url_selector=cfg.get("url_selector"),
                    url_attribute=url_attr,
                    image_selector=cfg.get("image_selector"),
                    image_attribute=img_attr,
                    currency=currency,
                    price_re=price_re,
                    ctx=ctx,
                )
            except Exception as exc:
                logger.debug("Generic HTML item rejected: %s", exc)
                continue
            if result is not None:
                results.append(result)
        return results

    @staticmethod
    def _text(node: Node | None) -> str | None:
        if node is None:
            return None
        text = node.text(separator=" ").strip()
        return text or None

    @staticmethod
    def _normalize(
        *,
        node: Node,
        base_url: str,
        name_selector: str,
        price_selector: str,
        url_selector: str | None,
        url_attribute: str,
        image_selector: str | None,
        image_attribute: str,
        currency: str,
        price_re: re.Pattern[str],
        ctx: SourceContext,
    ) -> ExternalProductResult | None:
        name = GenericHttpAdapter._text(node.css_first(name_selector))
        price_text = GenericHttpAdapter._text(node.css_first(price_selector))
        if not name or not price_text:
            return None

        match = price_re.search(price_text.replace(",", "."))
        if not match:
            return None
        try:
            price = _safe_decimal(match.group(1))
        except Exception:
            return None
        if price <= Decimal("0"):
            return None

        link_node = node.css_first(url_selector) if url_selector else node.css_first("a")
        href: str | None = None
        if link_node is not None:
            attrs: dict[str, Any] = dict(link_node.attributes or {})
            raw_href = attrs.get(url_attribute)
            if raw_href:
                href = urljoin(base_url, str(raw_href))

        image_node = node.css_first(image_selector) if image_selector else None
        image_url: str | None = None
        if image_node is not None:
            attrs = dict(image_node.attributes or {})
            raw_img = attrs.get(image_attribute)
            if raw_img:
                image_url = urljoin(base_url, str(raw_img))

        return ExternalProductResult(
            source_id=ctx.source.id,
            source_name=ctx.source.name,
            adapter_key=ctx.source.adapter_key,
            product_name=name[:512],
            description=None,
            sku=None,
            url=href,
            image_url=image_url,
            unit_price=price,
            currency=currency,
            lead_time_days=10,
            available_stock=9999,
            minimum_order_quantity=1,
            rating=ctx.source.reliability_rating,
            raw=None,
        )
