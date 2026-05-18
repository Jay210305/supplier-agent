"""Seed the configurable pool of external `CatalogSource` rows.

This file is intentionally separate from `backend/db/seed.py` (which loads
hard-coded local suppliers + their catalogs). Both can be run independently:

    docker exec fastapi python -m db.seed                  # local suppliers
    docker exec fastapi python -m db.seed_catalog_sources  # external sources

Upserts by `name`, so it is safe to re-run. Never truncates anything.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from models.catalog_source import CatalogSource
from models.enums import CatalogSourceKind


def _rows(*, enable_scraperapi: bool = False) -> list[CatalogSource]:
    scraper_enabled = enable_scraperapi
    return [
        CatalogSource(
            name="MercadoLibre Perú",
            kind=CatalogSourceKind.WEBSITE,
            adapter_key="mercadolibre",
            endpoint="https://api.mercadolibre.com",
            is_enabled=False,
            country="PE",
            currency="PEN",
            reliability_rating=Decimal("7.50"),
            rate_limit_per_min=15,
            timeout_seconds=12,
            auth={
                "access_token": "",
                "refresh_token": "",
                "client_id": "",
                "client_secret": "",
            },
            config={"site_id": "MPE"},
            notes=(
                "OAuth en developers.mercadolibre.com.pe; token en auth o MELI_* en .env. "
                "Usa /products/search (el endpoint /sites/.../search?q= ya no funciona)."
            ),
        ),
        CatalogSource(
            name="Amazon US",
            kind=CatalogSourceKind.WEBSITE,
            adapter_key="amazon",
            endpoint="https://webservices.amazon.com",
            is_enabled=False,
            country="US",
            currency="USD",
            reliability_rating=Decimal("8.00"),
            rate_limit_per_min=8,
            timeout_seconds=15,
            auth={"access_key": "", "secret_key": "", "partner_tag": "", "region": "us-east-1"},
            config={"marketplace": "www.amazon.com"},
            notes="Requiere credenciales PA-API 5. Activar tras configurar `auth`.",
        ),
        CatalogSource(
            name="eBay Global",
            kind=CatalogSourceKind.WEBSITE,
            adapter_key="ebay",
            endpoint="https://api.ebay.com",
            is_enabled=False,
            country="US",
            currency="USD",
            reliability_rating=Decimal("7.00"),
            rate_limit_per_min=10,
            timeout_seconds=15,
            auth={"oauth_token": ""},
            config={"marketplace_id": "EBAY_US"},
            notes="Requiere OAuth bearer token de la Browse API.",
        ),
        CatalogSource(
            name="Alibaba",
            kind=CatalogSourceKind.WEBSITE,
            adapter_key="alibaba",
            endpoint="https://api.alibaba.com",
            is_enabled=False,
            country="CN",
            currency="USD",
            reliability_rating=Decimal("6.50"),
            rate_limit_per_min=5,
            timeout_seconds=20,
            auth={"app_key": "", "app_secret": ""},
            config=None,
            notes="Open Platform: signing aún no implementado (stub).",
        ),
        CatalogSource(
            name="Linio Perú (genérico)",
            kind=CatalogSourceKind.WEBSITE,
            adapter_key="generic_http",
            endpoint="https://www.linio.com.pe",
            is_enabled=False,
            country="PE",
            currency="PEN",
            reliability_rating=Decimal("6.00"),
            rate_limit_per_min=6,
            timeout_seconds=20,
            auth=None,
            config={
                "search_url_template": "https://www.linio.com.pe/search?q={query}",
                "item_selector": "div.catalogue-product",
                "name_selector": "a.title-section",
                "price_selector": "span.price-main",
                "url_selector": "a.title-section",
                "url_attribute": "href",
                "image_selector": "img.image",
                "image_attribute": "src",
                "currency": "PEN",
            },
            notes="Plantilla genérica de scraping HTML. Ajustar selectores según el sitio real.",
        ),
        CatalogSource(
            name="ScraperAPI (MercadoLibre PE)",
            kind=CatalogSourceKind.WEBSITE,
            adapter_key="scraperapi",
            endpoint="http://api.scraperapi.com",
            is_enabled=scraper_enabled,
            country="PE",
            currency="PEN",
            reliability_rating=Decimal("7.00"),
            rate_limit_per_min=5,
            timeout_seconds=90,
            auth={"api_key": ""},
            config={
                "search_url_template": "https://listado.mercadolibre.com.pe/{query}",
                "query_format": "slug",
                "item_selector": "li.ui-search-layout__item",
                # ML nordic layout uses poly-component titles, not h2.
                "name_selector": "a.poly-component__title, h3",
                "price_selector": ".andes-money-amount",
                "url_selector": "a.poly-component__title",
                "url_attribute": "href",
                "image_selector": "img",
                "image_attribute": "src",
                "currency": "PEN",
                "price_regex": r"(\d{1,3}(?:\.\d{3})*)",
                "price_thousands_separator": ".",
                # ML PE serves a bot wall without JS; render=true is required.
                "render": True,
                "country_code": "pe",
            },
            notes=(
                "Plantilla ScraperAPI: setear api_key en auth o SCRAPERAPI_API_KEY en .env. "
                "Activar 'render: true' solo si el sitio carga precios con JavaScript "
                "(consume más créditos y aumenta latencia; subir timeout_seconds en consecuencia)."
            ),
        ),
        CatalogSource(
            name="ScraperAPI (Amazon US)",
            kind=CatalogSourceKind.WEBSITE,
            adapter_key="scraperapi",
            endpoint="http://api.scraperapi.com",
            is_enabled=scraper_enabled,
            country="US",
            currency="USD",
            reliability_rating=Decimal("7.50"),
            rate_limit_per_min=4,
            timeout_seconds=90,
            auth={"api_key": ""},
            config={
                "search_url_template": "https://www.amazon.com/s?k={query}",
                "query_format": "query",
                "item_selector": "div[data-component-type='s-search-result']",
                "name_selector": "h2 a span, h2 span, span.a-size-medium",
                "price_selector": ".a-price .a-offscreen",
                "price_regex": "\\$([\\d,]+(?:\\.\\d{2})?)",
                "url_selector": "a.a-link-normal[href*='/dp/']",
                "url_attribute": "href",
                "image_selector": "img.s-image",
                "image_attribute": "src",
                "currency": "USD",
                "render": True,
                "country_code": "us",
            },
            notes=(
                "Amazon SERP vía ScraperAPI: requiere `render: true` (consume créditos premium) "
                "y `country_code: us`. Configurar api_key en auth o SCRAPERAPI_API_KEY en .env. "
                "Subir timeout_seconds si Amazon devuelve la página antibot."
            ),
        ),
        CatalogSource(
            name="Proveedor RFQ por email",
            kind=CatalogSourceKind.EMAIL,
            adapter_key="email_rfq",
            endpoint="cotizaciones@proveedor-ejemplo.pe",
            is_enabled=False,
            country="PE",
            currency="PEN",
            reliability_rating=Decimal("5.00"),
            rate_limit_per_min=2,
            timeout_seconds=10,
            auth=None,
            config={"subject_template": "RFQ {request_id}: {query}"},
            notes="Las respuestas se ingestan asíncronamente y se cachean por query_hash.",
        ),
    ]


def seed() -> None:
    scraper_key = (settings.SCRAPERAPI_API_KEY or "").strip()
    engine = create_engine(settings.sync_database_url, future=True)
    Session = sessionmaker(bind=engine, future=True)
    with Session.begin() as session:
        for incoming in _rows(enable_scraperapi=bool(scraper_key)):
            existing = session.execute(
                select(CatalogSource).where(CatalogSource.name == incoming.name)
            ).scalar_one_or_none()
            if existing is None:
                session.add(incoming)
                continue
            for column in (
                "kind",
                "adapter_key",
                "endpoint",
                "country",
                "currency",
                "reliability_rating",
                "rate_limit_per_min",
                "timeout_seconds",
                "config",
                "notes",
            ):
                setattr(existing, column, getattr(incoming, column))
            # Never flip an enabled source off via re-seed.
            if scraper_key and incoming.adapter_key == "scraperapi":
                existing.is_enabled = True
            elif not existing.is_enabled and incoming.is_enabled:
                existing.is_enabled = True
            # Preserve user-supplied auth secrets; only fill if currently empty.
            if not existing.auth and incoming.auth:
                existing.auth = incoming.auth


def main() -> None:
    seed()


if __name__ == "__main__":
    main()
