"""Orchestrator that runs all enabled CatalogSource adapters in parallel.

Responsibilities:
- Resolve `CatalogSource` rows to adapter instances via the registry.
- Apply per-source semaphores (rate_limit_per_min) and per-source httpx timeout.
- Wrap the whole fan-out in a single `asyncio.wait_for` so `/procurement/parse`
  cannot block longer than `EXTERNAL_SEARCH_GLOBAL_TIMEOUT`.
- Read/write `catalog_search_cache` with TTL.
- Emit `EXTERNAL_SEARCH` rows in `procurement_logs` for auditability.

External hits are **never** persisted to the `products` table; they live only
in this JSONB cache and as transient `ExternalProductResult` objects.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.session import AsyncSessionLocal
from models.catalog_search_cache import CatalogSearchCache
from models.catalog_source import CatalogSource
from models.enums import LogSeverity
from models.procurement_log import ProcurementLog
from schemas.catalog_source import ExternalProductResult
from services.catalog_adapters import (
    AdapterAuthError,
    AdapterError,
    AdapterTimeoutError,
    SourceContext,
    get_adapter,
)

logger = logging.getLogger(__name__)


_EVENT_TYPE = "EXTERNAL_SEARCH"

# Adapters consulted first when the agent fans out to external sources.
# Operators can rely on ScraperAPI-backed pricing being checked before other
# providers so the parse report ranks those quotes earlier.
_PRIORITY_ADAPTER_KEYS: tuple[str, ...] = ("scraperapi",)


def is_priority_adapter(adapter_key: str) -> bool:
    return adapter_key in _PRIORITY_ADAPTER_KEYS


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()


def _merged_auth(source: CatalogSource) -> dict[str, Any]:
    """Source.auth overrides env-level fallbacks per adapter_key."""
    fallback: dict[str, Any] = {}
    key = source.adapter_key
    if key == "amazon":
        fallback = {
            "access_key": settings.AMAZON_PAAPI_ACCESS_KEY,
            "secret_key": settings.AMAZON_PAAPI_SECRET_KEY,
            "partner_tag": settings.AMAZON_PAAPI_PARTNER_TAG,
        }
    elif key == "ebay":
        fallback = {"oauth_token": settings.EBAY_OAUTH_TOKEN}
    elif key == "alibaba":
        fallback = {
            "app_key": settings.ALIBABA_APP_KEY,
            "app_secret": settings.ALIBABA_APP_SECRET,
        }
    elif key == "mercadolibre":
        fallback = {
            "access_token": settings.MELI_ACCESS_TOKEN,
            "refresh_token": settings.MELI_REFRESH_TOKEN,
            "client_id": settings.MELI_CLIENT_ID,
            "client_secret": settings.MELI_CLIENT_SECRET,
        }
    elif key == "scraperapi":
        fallback = {"api_key": settings.SCRAPERAPI_API_KEY}
    merged = {k: v for k, v in fallback.items() if v}
    if source.auth:
        merged.update({k: v for k, v in source.auth.items() if v not in (None, "")})
    return merged


async def _load_enabled_sources(
    session: AsyncSession, source_ids: list[int] | None = None
) -> list[CatalogSource]:
    stmt = select(CatalogSource).where(CatalogSource.is_enabled.is_(True))
    if source_ids:
        stmt = stmt.where(CatalogSource.id.in_(source_ids))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _read_cache(
    session: AsyncSession, source_id: int, qhash: str
) -> list[ExternalProductResult] | None:
    stmt = select(CatalogSearchCache).where(
        CatalogSearchCache.source_id == source_id,
        CatalogSearchCache.query_hash == qhash,
        CatalogSearchCache.expires_at > datetime.now(timezone.utc),
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    try:
        return [ExternalProductResult.model_validate(r) for r in row.results]
    except Exception:
        logger.warning("Cache row %s rejected by schema, deleting.", row.id)
        await session.execute(
            delete(CatalogSearchCache).where(CatalogSearchCache.id == row.id)
        )
        return None


async def _write_cache(
    session: AsyncSession,
    source_id: int,
    qhash: str,
    query_text: str,
    results: list[ExternalProductResult],
) -> None:
    ttl = timedelta(hours=settings.EXTERNAL_SEARCH_CACHE_TTL_HOURS)
    now = datetime.now(timezone.utc)
    # Upsert: delete any existing row then insert fresh
    await session.execute(
        delete(CatalogSearchCache).where(
            CatalogSearchCache.source_id == source_id,
            CatalogSearchCache.query_hash == qhash,
        )
    )
    session.add(
        CatalogSearchCache(
            source_id=source_id,
            query_hash=qhash,
            query_text=query_text[:512],
            results=[r.model_dump(mode="json") for r in results],
            fetched_at=now,
            expires_at=now + ttl,
        )
    )


async def _log(
    session: AsyncSession,
    source: CatalogSource | None,
    *,
    event: str,
    severity: LogSeverity,
    message: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        ProcurementLog(
            event_type=_EVENT_TYPE,
            event_source=source.name if source else None,
            message=f"{event}: {message}"[:2000],
            payload=payload,
            severity=severity,
        )
    )


def _select_top_per_query(
    results: list[ExternalProductResult], limit: int
) -> list[ExternalProductResult]:
    return sorted(results, key=lambda r: (r.unit_price, -r.available_stock))[:limit]


async def _run_one(
    *,
    source: CatalogSource,
    query: str,
    limit: int,
    qhash: str,
    semaphore: asyncio.Semaphore,
) -> tuple[int, list[ExternalProductResult]]:
    """Run one adapter using its own AsyncSession (concurrency-safe)."""
    async with AsyncSessionLocal() as session:
        cached = await _read_cache(session, source.id, qhash)
        if cached is not None:
            await _log(
                session,
                source,
                event="cache_hit",
                severity=LogSeverity.DEBUG,
                message=f"query={query!r} hits={len(cached)}",
                payload={"query": query, "source_id": source.id, "hits": len(cached)},
            )
            await session.commit()
            return source.id, _select_top_per_query(cached, limit)

        adapter_cls = get_adapter(source.adapter_key)
        if adapter_cls is None:
            await _log(
                session,
                source,
                event="adapter_missing",
                severity=LogSeverity.WARNING,
                message=f"unknown adapter_key={source.adapter_key!r}",
                payload={"query": query, "source_id": source.id},
            )
            await session.commit()
            return source.id, []

        adapter = adapter_cls()
        timeout = httpx.Timeout(source.timeout_seconds, connect=min(source.timeout_seconds, 5))
        started = time.perf_counter()
        try:
            async with semaphore:
                async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
                    ctx = SourceContext(
                        source=source,
                        client=client,
                        auth=_merged_auth(source),
                        config=source.config or {},
                    )
                    hits = await adapter.search(query=query, limit=limit, ctx=ctx)
        except (AdapterAuthError, AdapterTimeoutError, AdapterError) as e:
            elapsed = int((time.perf_counter() - started) * 1000)
            event_map = {
                AdapterAuthError: "auth_error",
                AdapterTimeoutError: "timeout",
                AdapterError: "adapter_error",
            }
            await _log(
                session,
                source,
                event=event_map[type(e)],
                severity=LogSeverity.WARNING,
                message=str(e),
                payload={"query": query, "source_id": source.id, "elapsed_ms": elapsed},
            )
            await session.commit()
            return source.id, []
        except Exception as e:  # noqa: BLE001
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.exception("Adapter %s crashed", source.adapter_key)
            await _log(
                session,
                source,
                event="adapter_crash",
                severity=LogSeverity.ERROR,
                message=f"{type(e).__name__}: {e}",
                payload={"query": query, "source_id": source.id, "elapsed_ms": elapsed},
            )
            await session.commit()
            return source.id, []

        elapsed = int((time.perf_counter() - started) * 1000)
        await _write_cache(session, source.id, qhash, query, hits)
        await _log(
            session,
            source,
            event="ok",
            severity=LogSeverity.INFO,
            message=f"query={query!r} hits={len(hits)} elapsed_ms={elapsed}",
            payload={
                "query": query,
                "source_id": source.id,
                "hits": len(hits),
                "elapsed_ms": elapsed,
            },
        )
        await session.commit()
        return source.id, _select_top_per_query(hits, limit)


async def search_one_query(
    session: AsyncSession,
    query: str,
    *,
    limit: int | None = None,
    source_ids: list[int] | None = None,
) -> dict[int, list[ExternalProductResult]]:
    """Run all enabled adapters for a single query string.

    `session` is used only to load `CatalogSource` rows and to write the
    `global_timeout` log on failure. Each adapter coroutine opens its own
    session via `AsyncSessionLocal()` to keep concurrent DB I/O safe.
    """
    if not settings.EXTERNAL_SEARCH_ENABLED:
        return {}

    effective_limit = limit or settings.EXTERNAL_SEARCH_DEFAULT_LIMIT
    sources = await _load_enabled_sources(session, source_ids)
    if not sources:
        return {}

    # Detach so coroutines can hold the row safely after `session` closes.
    for s in sources:
        session.expunge(s)

    qhash = _query_hash(query)
    semaphores: dict[int, asyncio.Semaphore] = {
        s.id: asyncio.Semaphore(max(1, min(s.rate_limit_per_min, 20))) for s in sources
    }

    # Phase 1: priority adapters (ScraperAPI). Phase 2: everything else.
    # Sharing the same wall-clock budget keeps `/procurement/parse` bounded.
    priority = [s for s in sources if is_priority_adapter(s.adapter_key)]
    rest = [s for s in sources if not is_priority_adapter(s.adapter_key)]
    phases = [p for p in (priority, rest) if p]

    results: dict[int, list[ExternalProductResult]] = {}
    deadline = asyncio.get_event_loop().time() + settings.EXTERNAL_SEARCH_GLOBAL_TIMEOUT

    for phase_idx, phase_sources in enumerate(phases):
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            async with AsyncSessionLocal() as log_session:
                await _log(
                    log_session,
                    None,
                    event="global_timeout",
                    severity=LogSeverity.WARNING,
                    message=(
                        f"query={query!r} phase={phase_idx} skipped "
                        f"(no time left within {settings.EXTERNAL_SEARCH_GLOBAL_TIMEOUT}s)"
                    ),
                    payload={"query": query, "phase": phase_idx},
                )
                await log_session.commit()
            break

        coros = [
            _run_one(
                source=s,
                query=query,
                limit=effective_limit,
                qhash=qhash,
                semaphore=semaphores[s.id],
            )
            for s in phase_sources
        ]
        try:
            gathered = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=False),
                timeout=remaining,
            )
        except asyncio.TimeoutError:
            async with AsyncSessionLocal() as log_session:
                await _log(
                    log_session,
                    None,
                    event="global_timeout",
                    severity=LogSeverity.WARNING,
                    message=(
                        f"query={query!r} phase={phase_idx} "
                        f"timeout={settings.EXTERNAL_SEARCH_GLOBAL_TIMEOUT}s"
                    ),
                    payload={"query": query, "phase": phase_idx},
                )
                await log_session.commit()
            break
        for source_id, hits in gathered:
            results[source_id] = hits or []

    return results


async def search_many_queries(
    session: AsyncSession,
    queries: Iterable[str],
    *,
    limit: int | None = None,
    source_ids: list[int] | None = None,
) -> dict[int, dict[str, list[ExternalProductResult]]]:
    """Run `search_one_query` for each query and return nested results.

    Shape: `{source_id: {query: results}}`. Used by the candidate aggregator
    when a procurement request has multiple line items.
    """
    out: dict[int, dict[str, list[ExternalProductResult]]] = defaultdict(dict)
    for q in queries:
        per_source = await search_one_query(
            session, q, limit=limit, source_ids=source_ids
        )
        for src_id, hits in per_source.items():
            out[src_id][q] = hits
    return dict(out)
