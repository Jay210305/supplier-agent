"""Email RFQ adapter — never participates in synchronous scoring.

Email-based suppliers can't answer in real time; they get a Request-For-Quote
sent out via SMTP / n8n and reply asynchronously. Those replies are parsed by
the Ollama entity extractor and seeded back into `catalog_search_cache` under
the same `query_hash`, where the next synchronous call will pick them up.

Right now this adapter simply queues nothing and returns an empty list, so
enabling it does not break the pipeline. The actual RFQ dispatch is owned by
n8n + the email service (out of scope for this slice).
"""

from __future__ import annotations

import logging

from models.enums import CatalogSourceKind
from schemas.catalog_source import ExternalProductResult
from services.catalog_adapters.base import (
    AdapterMetadata,
    CatalogAdapter,
    SourceContext,
)

logger = logging.getLogger(__name__)


class EmailRFQAdapter(CatalogAdapter):
    metadata = AdapterMetadata(
        key="email_rfq",
        kind=CatalogSourceKind.EMAIL,
        description="Outbound RFQ via email; replies are ingested asynchronously.",
        requires_auth=False,
        config_fields=("subject_template",),
    )

    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        logger.info(
            "email_rfq adapter: would enqueue RFQ to %s for query=%r (not implemented).",
            ctx.source.endpoint,
            query,
        )
        return []
