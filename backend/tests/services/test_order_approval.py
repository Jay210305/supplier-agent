from __future__ import annotations

import pytest

from models.enums import PurchaseOrderStatus
from services.order_approval import resolve_approval_status


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Approved", PurchaseOrderStatus.APPROVED),
        ("approve", PurchaseOrderStatus.APPROVED),
        ("Reject", PurchaseOrderStatus.REJECTED),
        ("rejected", PurchaseOrderStatus.REJECTED),
        ("Needs Review", PurchaseOrderStatus.NEEDS_REVIEW),
        ("NEEDS_REVIEW", PurchaseOrderStatus.NEEDS_REVIEW),
    ],
)
def test_resolve_approval_status(raw: str, expected: PurchaseOrderStatus) -> None:
    assert resolve_approval_status(raw) == expected


def test_resolve_approval_status_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid approval status"):
        resolve_approval_status("maybe")
