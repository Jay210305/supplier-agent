from __future__ import annotations

import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.catalog_source import CatalogSource
from schemas.catalog_source import (
    AdapterInfo,
    CatalogSourceCreate,
    CatalogSourceRead,
    CatalogSourceUpdate,
    ExternalSearchBody,
    ExternalSearchResponse,
    TestSourceBody,
    TestSourceResponse,
)
from services.catalog_adapters import (
    AdapterError,
    SourceContext,
    get_adapter,
    list_adapters,
)
from services.catalog_search import _merged_auth, search_one_query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/adapters", response_model=list[AdapterInfo])
async def list_available_adapters() -> list[AdapterInfo]:
    return [
        AdapterInfo(
            key=meta.key,
            kind=meta.kind,
            description=meta.description,
            requires_auth=meta.requires_auth,
            auth_fields=list(meta.auth_fields),
            config_fields=list(meta.config_fields),
        )
        for meta in list_adapters()
    ]


@router.get("", response_model=list[CatalogSourceRead])
async def list_sources(
    enabled_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> list[CatalogSourceRead]:
    stmt = select(CatalogSource).order_by(CatalogSource.id)
    if enabled_only:
        stmt = stmt.where(CatalogSource.is_enabled.is_(True))
    result = await db.execute(stmt)
    return [CatalogSourceRead.model_validate(row) for row in result.scalars().all()]


@router.post("", response_model=CatalogSourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: CatalogSourceCreate, db: AsyncSession = Depends(get_db)
) -> CatalogSourceRead:
    if get_adapter(body.adapter_key) is None:
        raise HTTPException(
            status_code=422, detail=f"Unknown adapter_key: {body.adapter_key!r}"
        )
    row = CatalogSource(**body.model_dump())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Source name already exists") from e
    await db.refresh(row)
    return CatalogSourceRead.model_validate(row)


@router.get("/{source_id}", response_model=CatalogSourceRead)
async def get_source(source_id: int, db: AsyncSession = Depends(get_db)) -> CatalogSourceRead:
    row = await db.get(CatalogSource, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Catalog source not found")
    return CatalogSourceRead.model_validate(row)


@router.patch("/{source_id}", response_model=CatalogSourceRead)
async def update_source(
    source_id: int,
    body: CatalogSourceUpdate,
    db: AsyncSession = Depends(get_db),
) -> CatalogSourceRead:
    row = await db.get(CatalogSource, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Catalog source not found")
    changes = body.model_dump(exclude_unset=True)
    if "adapter_key" in changes and get_adapter(changes["adapter_key"]) is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown adapter_key: {changes['adapter_key']!r}",
        )
    for k, v in changes.items():
        setattr(row, k, v)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Source name already exists") from e
    await db.refresh(row)
    return CatalogSourceRead.model_validate(row)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)) -> None:
    row = await db.get(CatalogSource, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Catalog source not found")
    await db.delete(row)
    await db.commit()


@router.post("/{source_id}/test", response_model=TestSourceResponse)
async def test_source(
    source_id: int,
    body: TestSourceBody | None = None,
    db: AsyncSession = Depends(get_db),
) -> TestSourceResponse:
    """One-shot adapter check that does NOT touch the cache.

    Returns up to `body.limit` normalized hits or the adapter's error message.
    Used by the frontend's "Test source" button.
    """
    row = await db.get(CatalogSource, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Catalog source not found")

    body = body or TestSourceBody()
    adapter_cls = get_adapter(row.adapter_key)
    if adapter_cls is None:
        raise HTTPException(
            status_code=422, detail=f"Unknown adapter_key: {row.adapter_key!r}"
        )

    adapter = adapter_cls()
    timeout = httpx.Timeout(row.timeout_seconds, connect=min(row.timeout_seconds, 5))
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
            ctx = SourceContext(
                source=row,
                client=client,
                auth=_merged_auth(row),
                config=row.config or {},
            )
            hits = await adapter.search(query=body.query, limit=body.limit, ctx=ctx)
    except AdapterError as e:
        elapsed = int((time.perf_counter() - started) * 1000)
        return TestSourceResponse(
            source_id=row.id,
            source_name=row.name,
            adapter_key=row.adapter_key,
            query=body.query,
            elapsed_ms=elapsed,
            ok=False,
            error=str(e),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("test_source crashed for source %s", source_id)
        elapsed = int((time.perf_counter() - started) * 1000)
        return TestSourceResponse(
            source_id=row.id,
            source_name=row.name,
            adapter_key=row.adapter_key,
            query=body.query,
            elapsed_ms=elapsed,
            ok=False,
            error=f"{type(e).__name__}: {e}",
        )

    elapsed = int((time.perf_counter() - started) * 1000)
    return TestSourceResponse(
        source_id=row.id,
        source_name=row.name,
        adapter_key=row.adapter_key,
        query=body.query,
        elapsed_ms=elapsed,
        ok=True,
        results=hits,
    )


@router.post("/search", response_model=ExternalSearchResponse)
async def search_external(
    body: ExternalSearchBody, db: AsyncSession = Depends(get_db)
) -> ExternalSearchResponse:
    """Run the cached fan-out search across all enabled sources for a single query."""
    started = time.perf_counter()
    per_source = await search_one_query(
        db, body.query, limit=body.limit, source_ids=body.source_ids
    )
    elapsed = int((time.perf_counter() - started) * 1000)

    sources_used: list[str] = []
    flattened = []
    for src_id, hits in per_source.items():
        if hits:
            sources_used.append(hits[0].source_name)
        else:
            row = await db.get(CatalogSource, src_id)
            if row is not None:
                sources_used.append(row.name)
        flattened.extend(hits)

    flattened.sort(key=lambda r: r.unit_price)
    return ExternalSearchResponse(
        query=body.query,
        sources_used=sources_used,
        elapsed_ms=elapsed,
        results=flattened[: body.limit],
    )
