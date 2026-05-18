"""Adapter-level tests with respx-mocked HTTP."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx

from models.catalog_source import CatalogSource
from models.enums import CatalogSourceKind
from services.catalog_adapters import (
    AdapterAuthError,
    AdapterError,
    SourceContext,
)
from services.catalog_adapters.amazon import AmazonAdapter
from services.catalog_adapters.ebay import EbayAdapter
from services.catalog_adapters.email_rfq import EmailRFQAdapter
from services.catalog_adapters.generic_http import GenericHttpAdapter, format_query_for_template
from services.catalog_adapters.mercadolibre import MercadoLibreAdapter
from services.catalog_adapters.scraperapi import (
    SCRAPERAPI_ENDPOINT,
    ScraperApiAdapter,
)


def _source(adapter_key: str, **overrides) -> CatalogSource:
    defaults = dict(
        id=1,
        name="Test Source",
        kind=CatalogSourceKind.WEBSITE,
        adapter_key=adapter_key,
        endpoint="https://example.com",
        is_enabled=True,
        country="PE",
        currency="PEN",
        reliability_rating=Decimal("7.50"),
        rate_limit_per_min=10,
        timeout_seconds=5,
        auth=None,
        config=None,
        notes=None,
    )
    defaults.update(overrides)
    return CatalogSource(**defaults)


@pytest.mark.asyncio
@respx.mock
async def test_mercadolibre_requires_access_token() -> None:
    source = _source("mercadolibre", endpoint="https://api.mercadolibre.com")
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client, auth={})
        with pytest.raises(AdapterAuthError):
            await MercadoLibreAdapter().search("laptop", 5, ctx)


@pytest.mark.asyncio
@respx.mock
async def test_mercadolibre_parses_catalog_search() -> None:
    source = _source(
        "mercadolibre",
        endpoint="https://api.mercadolibre.com",
        config={"site_id": "MPE"},
    )
    search_route = respx.get("https://api.mercadolibre.com/products/search").respond(
        json={
            "results": [
                {"id": "MPE1", "name": "Laptop Lenovo IdeaPad 3"},
                {"id": "MPE2", "name": "Laptop HP 14"},
            ]
        }
    )
    respx.get("https://api.mercadolibre.com/products/MPE1").respond(
        json={
            "id": "MPE1",
            "name": "Laptop Lenovo IdeaPad 3",
            "permalink": "https://articulo.mercadolibre.com.pe/p/MPE1",
            "pictures": [{"url": "https://img/1.jpg"}],
            "buy_box_winner": {
                "item_id": "MPE1001",
                "price": 2499.0,
                "currency_id": "PEN",
                "available_quantity": 5,
                "condition": "new",
                "seller_id": 99,
                "shipping": {"logistic_type": "fulfillment"},
            },
        }
    )
    respx.get("https://api.mercadolibre.com/products/MPE2").respond(
        json={
            "id": "MPE2",
            "name": "Laptop HP 14",
            "buy_box_winner_price_range": {
                "min": {"price": "1990.50", "currency_id": "PEN"},
                "max": {"price": 2200, "currency_id": "PEN"},
            },
        }
    )
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(
            source=source,
            client=client,
            auth={"access_token": "APP_USR-test-token"},
            config={"site_id": "MPE"},
        )
        results = await MercadoLibreAdapter().search("laptop", 10, ctx)

    assert search_route.calls.last.request.headers["Authorization"] == "Bearer APP_USR-test-token"
    assert len(results) == 2
    first = results[0]
    assert first.product_name == "Laptop Lenovo IdeaPad 3"
    assert first.unit_price == Decimal("2499.00")
    assert first.currency == "PEN"
    assert first.lead_time_days == 2
    assert first.available_stock == 5
    assert results[1].unit_price == Decimal("1990.50")
    assert results[1].lead_time_days == 7
    assert results[1].available_stock == 9999


@pytest.mark.asyncio
@respx.mock
async def test_mercadolibre_http_error_raises_adapter_error() -> None:
    source = _source("mercadolibre")
    respx.get("https://example.com/products/search").respond(status_code=500, text="boom")
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(
            source=source,
            client=client,
            auth={"access_token": "APP_USR-test-token"},
        )
        with pytest.raises(AdapterError):
            await MercadoLibreAdapter().search("laptop", 5, ctx)


@pytest.mark.asyncio
async def test_amazon_requires_credentials() -> None:
    source = _source("amazon", endpoint="https://webservices.amazon.com")
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client, auth={})
        with pytest.raises(AdapterAuthError):
            await AmazonAdapter().search("laptop", 5, ctx)


@pytest.mark.asyncio
@respx.mock
async def test_ebay_parses_browse_api() -> None:
    source = _source("ebay", endpoint="https://api.ebay.com")
    respx.get("https://api.ebay.com/buy/browse/v1/item_summary/search").respond(
        json={
            "itemSummaries": [
                {
                    "itemId": "v1|123|0",
                    "title": "Dell XPS 13",
                    "shortDescription": "i7 16GB",
                    "price": {"value": "1299.99", "currency": "USD"},
                    "itemWebUrl": "https://ebay.com/itm/123",
                    "image": {"imageUrl": "https://img/x.jpg"},
                    "condition": "New",
                    "buyingOptions": ["FIXED_PRICE"],
                }
            ]
        }
    )
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(
            source=source,
            client=client,
            auth={"oauth_token": "tok"},
        )
        results = await EbayAdapter().search("laptop", 5, ctx)
    assert len(results) == 1
    assert results[0].unit_price == Decimal("1299.99")
    assert results[0].currency == "USD"


@pytest.mark.asyncio
async def test_ebay_auth_required() -> None:
    source = _source("ebay")
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client, auth={})
        with pytest.raises(AdapterAuthError):
            await EbayAdapter().search("laptop", 5, ctx)


@pytest.mark.asyncio
@respx.mock
async def test_generic_http_extracts_with_selectors() -> None:
    html = """
    <html><body>
      <li class="product">
        <h2 class="title">Silla ergonómica</h2>
        <span class="price">S/ 899.00</span>
        <a class="product-link" href="/sillas/1">link</a>
        <img src="/img/1.jpg" />
      </li>
      <li class="product">
        <h2 class="title">Silla básica</h2>
        <span class="price">S/ 199,90</span>
        <a class="product-link" href="https://shop.example.com/sillas/2">link</a>
      </li>
    </body></html>
    """
    source = _source(
        "generic_http",
        endpoint="https://shop.example.com",
        config={
            "search_url_template": "https://shop.example.com/search?q={query}",
            "item_selector": "li.product",
            "name_selector": "h2.title",
            "price_selector": "span.price",
            "url_selector": "a.product-link",
            "image_selector": "img",
        },
    )
    respx.get("https://shop.example.com/search").respond(html=html)
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(
            source=source,
            client=client,
            config=source.config or {},
        )
        results = await GenericHttpAdapter().search("silla", 5, ctx)

    assert len(results) == 2
    assert results[0].product_name == "Silla ergonómica"
    assert results[0].unit_price == Decimal("899.00")
    assert results[0].url == "https://shop.example.com/sillas/1"
    assert results[0].image_url == "https://shop.example.com/img/1.jpg"
    assert results[1].unit_price == Decimal("199.90")


@pytest.mark.asyncio
@respx.mock
async def test_generic_http_dot_thousands_price() -> None:
    html = """
    <html><body>
      <li class="item">
        <a class="poly-component__title" href="/p/1">Consola Playstation 5</a>
        <span class="andes-money-amount">S/2.799</span>
      </li>
    </body></html>
    """
    source = _source(
        "generic_http",
        endpoint="https://listado.mercadolibre.com.pe",
        config={
            "search_url_template": "https://listado.mercadolibre.com.pe/{query}",
            "query_format": "slug",
            "item_selector": "li.item",
            "name_selector": "a.poly-component__title",
            "price_selector": ".andes-money-amount",
            "price_regex": r"(\d{1,3}(?:\.\d{3})*)",
            "price_thousands_separator": ".",
            "currency": "PEN",
        },
    )
    respx.get("https://listado.mercadolibre.com.pe/playstation-5").respond(html=html)
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client, config=source.config or {})
        results = await GenericHttpAdapter().search("playstation 5", 5, ctx)

    assert len(results) == 1
    assert results[0].unit_price == Decimal("2799")
    assert results[0].currency == "PEN"


_SCRAPER_HTML = """
<html><body>
  <li class="product">
    <h2 class="title">Laptop Lenovo IdeaPad</h2>
    <span class="price">S/ 2499.00</span>
    <a class="product-link" href="/laptops/1">link</a>
    <img src="/img/1.jpg" />
  </li>
</body></html>
"""


def _scraperapi_source(**overrides) -> CatalogSource:
    config: dict = {
        "search_url_template": "https://shop.example.com/search?q={query}",
        "item_selector": "li.product",
        "name_selector": "h2.title",
        "price_selector": "span.price",
        "url_selector": "a.product-link",
        "image_selector": "img",
    }
    config.update(overrides.pop("config", {}) or {})
    return _source("scraperapi", endpoint=SCRAPERAPI_ENDPOINT, config=config, **overrides)


@pytest.mark.asyncio
@respx.mock
async def test_scraperapi_requires_api_key() -> None:
    source = _scraperapi_source()
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client, auth={}, config=source.config or {})
        with pytest.raises(AdapterAuthError):
            await ScraperApiAdapter().search("laptop", 5, ctx)


@pytest.mark.asyncio
@respx.mock
async def test_scraperapi_omits_render_when_disabled() -> None:
    source = _scraperapi_source()
    route = respx.get(SCRAPERAPI_ENDPOINT).respond(html=_SCRAPER_HTML)
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(
            source=source,
            client=client,
            auth={"api_key": "test-key"},
            config=source.config or {},
        )
        results = await ScraperApiAdapter().search("laptop", 5, ctx)

    assert len(results) == 1
    assert results[0].unit_price == Decimal("2499.00")
    # Relative href resolved against the *target* URL (the scraped site),
    # not the api.scraperapi.com proxy endpoint.
    assert results[0].url == "https://shop.example.com/laptops/1"

    request = route.calls.last.request
    qp = request.url.params
    assert qp["api_key"] == "test-key"
    assert qp["url"] == "https://shop.example.com/search?q=laptop"
    assert "render" not in qp


@pytest.mark.asyncio
@respx.mock
async def test_scraperapi_passes_render_true_when_enabled() -> None:
    source = _scraperapi_source(
        config={"render": True, "country_code": "pe", "device_type": "desktop"}
    )
    route = respx.get(SCRAPERAPI_ENDPOINT).respond(html=_SCRAPER_HTML)
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(
            source=source,
            client=client,
            auth={"api_key": "test-key"},
            config=source.config or {},
        )
        await ScraperApiAdapter().search("laptop", 5, ctx)

    qp = route.calls.last.request.url.params
    assert qp["render"] == "true"
    assert qp["country_code"] == "pe"
    assert qp["device_type"] == "desktop"
    assert "premium" not in qp


@pytest.mark.asyncio
async def test_scraperapi_premium_conflict_raises() -> None:
    source = _scraperapi_source(config={"premium": True, "ultra_premium": True})
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(
            source=source,
            client=client,
            auth={"api_key": "test-key"},
            config=source.config or {},
        )
        with pytest.raises(AdapterError):
            await ScraperApiAdapter().search("laptop", 5, ctx)


def test_format_query_slug_for_listado() -> None:
    tpl = "https://listado.mercadolibre.com.pe/{query}"
    assert (
        format_query_for_template("playstation 5", tpl, {"query_format": "slug"})
        == "playstation-5"
    )


def test_format_query_for_search_param() -> None:
    tpl = "https://www.amazon.com/s?k={query}"
    assert format_query_for_template("playstation 5", tpl, {}) == "playstation+5"


@pytest.mark.asyncio
async def test_email_rfq_returns_empty() -> None:
    source = _source("email_rfq", kind=CatalogSourceKind.EMAIL, endpoint="rfq@x.pe")
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client)
        results = await EmailRFQAdapter().search("anything", 5, ctx)
    assert results == []
