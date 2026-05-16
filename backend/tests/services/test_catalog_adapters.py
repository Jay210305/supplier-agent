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
from services.catalog_adapters.generic_http import GenericHttpAdapter
from services.catalog_adapters.mercadolibre import MercadoLibreAdapter


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
async def test_mercadolibre_parses_public_search() -> None:
    source = _source(
        "mercadolibre",
        endpoint="https://api.mercadolibre.com",
        config={"site_id": "MPE"},
    )
    respx.get("https://api.mercadolibre.com/sites/MPE/search").respond(
        json={
            "results": [
                {
                    "id": "MPE1",
                    "title": "Laptop Lenovo IdeaPad 3",
                    "price": 2499.0,
                    "currency_id": "PEN",
                    "available_quantity": 5,
                    "permalink": "https://articulo.mercadolibre.com.pe/MPE1",
                    "thumbnail": "https://img/1.jpg",
                    "condition": "new",
                    "seller": {"id": 99},
                    "shipping": {"logistic_type": "fulfillment"},
                },
                {
                    "id": "MPE2",
                    "title": "Laptop HP 14",
                    "price": "1990.50",
                    "currency_id": "PEN",
                    "available_quantity": 0,
                    "permalink": "https://articulo.mercadolibre.com.pe/MPE2",
                    "shipping": {"logistic_type": "drop_off"},
                },
            ]
        }
    )
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client, config={"site_id": "MPE"})
        results = await MercadoLibreAdapter().search("laptop", 10, ctx)

    assert len(results) == 2
    first = results[0]
    assert first.product_name == "Laptop Lenovo IdeaPad 3"
    assert first.unit_price == Decimal("2499.00")
    assert first.currency == "PEN"
    assert first.lead_time_days == 2  # fulfillment shortcut
    assert first.available_stock == 5
    assert results[1].lead_time_days == 7  # drop_off fallback
    assert results[1].available_stock == 9999  # 0 → fallback


@pytest.mark.asyncio
@respx.mock
async def test_mercadolibre_http_error_raises_adapter_error() -> None:
    source = _source("mercadolibre")
    respx.get("https://example.com/sites/MPE/search").respond(status_code=500, text="boom")
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client)
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
async def test_email_rfq_returns_empty() -> None:
    source = _source("email_rfq", kind=CatalogSourceKind.EMAIL, endpoint="rfq@x.pe")
    async with httpx.AsyncClient(timeout=5) as client:
        ctx = SourceContext(source=source, client=client)
        results = await EmailRFQAdapter().search("anything", 5, ctx)
    assert results == []
