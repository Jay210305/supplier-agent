"""Adapter registry for external catalog sources.

Each adapter is registered by `adapter_key` (the value stored on
`CatalogSource.adapter_key`). The orchestrator (`services/catalog_search.py`)
resolves the key into a concrete `CatalogAdapter` instance.
"""

from __future__ import annotations

from services.catalog_adapters.alibaba import AlibabaAdapter
from services.catalog_adapters.amazon import AmazonAdapter
from services.catalog_adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterMetadata,
    AdapterTimeoutError,
    CatalogAdapter,
    SourceContext,
)
from services.catalog_adapters.ebay import EbayAdapter
from services.catalog_adapters.email_rfq import EmailRFQAdapter
from services.catalog_adapters.generic_http import GenericHttpAdapter
from services.catalog_adapters.mercadolibre import MercadoLibreAdapter
from services.catalog_adapters.scraperapi import ScraperApiAdapter

ADAPTERS: dict[str, type[CatalogAdapter]] = {
    ScraperApiAdapter.metadata.key: ScraperApiAdapter,
    MercadoLibreAdapter.metadata.key: MercadoLibreAdapter,
    AmazonAdapter.metadata.key: AmazonAdapter,
    EbayAdapter.metadata.key: EbayAdapter,
    AlibabaAdapter.metadata.key: AlibabaAdapter,
    GenericHttpAdapter.metadata.key: GenericHttpAdapter,
    EmailRFQAdapter.metadata.key: EmailRFQAdapter,
}


def list_adapters() -> list[AdapterMetadata]:
    return [cls.metadata for cls in ADAPTERS.values()]


def get_adapter(key: str) -> type[CatalogAdapter] | None:
    return ADAPTERS.get(key)


__all__ = [
    "ADAPTERS",
    "AdapterAuthError",
    "AdapterError",
    "AdapterMetadata",
    "AdapterTimeoutError",
    "CatalogAdapter",
    "SourceContext",
    "get_adapter",
    "list_adapters",
]
