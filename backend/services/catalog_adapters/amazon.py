"""Amazon adapter — requires PA-API 5 credentials.

This file ships disabled-by-default: scraping amazon.com HTML is against ToS
and is unreliable. To actually fetch results, populate `auth` on the
`CatalogSource`:
  {"access_key": "...", "secret_key": "...", "partner_tag": "...", "region": "us-east-1"}
and (optionally) provide `config = {"marketplace": "www.amazon.com"}`.

The signing logic is intentionally not implemented here (it requires AWS SigV4
of the JSON payload). The hook below returns empty + a warning so the rest of
the pipeline keeps working. Implement `_call_paapi` to enable real fetches.
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


class AmazonAdapter(CatalogAdapter):
    metadata = AdapterMetadata(
        key="amazon",
        kind=CatalogSourceKind.WEBSITE,
        description="Amazon Product Advertising API 5 (requires AWS SigV4 credentials).",
        requires_auth=True,
        auth_fields=("access_key", "secret_key", "partner_tag", "region"),
        config_fields=("marketplace",),
    )

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        required = ("access_key", "secret_key", "partner_tag")
        if not all(ctx.auth.get(k) for k in required):
            raise AdapterAuthError(
                "Amazon PA-API credentials missing (access_key/secret_key/partner_tag)."
            )

        logger.warning(
            "Amazon PA-API SigV4 call not implemented yet; returning empty results "
            "for query=%r on source=%r. Implement AmazonAdapter._call_paapi.",
            query,
            ctx.source.name,
        )
        return []
