from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx

from models.enums import CatalogSourceKind
from schemas.catalog_source import ExternalProductResult

if TYPE_CHECKING:
    from models.catalog_source import CatalogSource


@dataclass(frozen=True)
class AdapterMetadata:
    key: str
    kind: CatalogSourceKind
    description: str
    requires_auth: bool = False
    auth_fields: tuple[str, ...] = ()
    config_fields: tuple[str, ...] = ()


@dataclass
class SourceContext:
    """Per-request context handed to an adapter."""

    source: CatalogSource
    client: httpx.AsyncClient
    auth: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)


class AdapterError(Exception):
    """Recoverable adapter failure — search returns empty for this source."""


class AdapterAuthError(AdapterError):
    """Adapter cannot run because credentials are missing or invalid."""


class AdapterTimeoutError(AdapterError):
    """External service did not respond within configured timeout."""


class CatalogAdapter(ABC):
    """Subclass and set `metadata`. One adapter per external integration."""

    metadata: AdapterMetadata

    @abstractmethod
    async def search(
        self, query: str, limit: int, ctx: SourceContext
    ) -> list[ExternalProductResult]:
        """Return up to `limit` normalized hits for `query`. Empty list = no results."""
        raise NotImplementedError


def _safe_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        if value is None or value == "":
            return Decimal(default)
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal(default)
