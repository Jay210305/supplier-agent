"""Alibaba Open Platform adapter stub.

Real integration requires Alibaba Open Platform credentials and a signed
request flow. Populate `auth` with `{"app_key": "...", "app_secret": "..."}`.
Until the signing logic is implemented, this adapter returns empty + warns.
"""

from __future__ import annotations

import logging

from models.enums import CatalogSourceKind
from schemas.catalog_source import ExternalProductResult
from services.catalog_adapters.base import (
    AdapterAuthError,
    AdapterMetadata,
    CatalogAdapter,
    SourceContext,
)

logger = logging.getLogger(__name__)


class AlibabaAdapter(CatalogAdapter):
    metadata = AdapterMetadata(
        key="alibaba",
        kind=CatalogSourceKind.WEBSITE,
        description="Alibaba Open Platform (requires app_key/app_secret).",
        requires_auth=True,
        auth_fields=("app_key", "app_secret"),
    )

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        if not (ctx.auth.get("app_key") and ctx.auth.get("app_secret")):
            raise AdapterAuthError("Alibaba app_key/app_secret missing.")
        logger.warning(
            "Alibaba Open Platform signing not implemented yet; returning empty for query=%r.",
            query,
        )
        return []
