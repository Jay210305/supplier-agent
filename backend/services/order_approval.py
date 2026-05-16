"""Update purchase order status after human approval (n8n webhook path)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import LogSeverity, PurchaseOrderStatus
from models.procurement_log import ProcurementLog
from models.purchase_order import PurchaseOrder
from schemas.purchase_order import OrderApproveBody, OrderApproveResponse

logger = logging.getLogger(__name__)

_STATUS_ALIASES: dict[str, PurchaseOrderStatus] = {
    "approved": PurchaseOrderStatus.APPROVED,
    "approve": PurchaseOrderStatus.APPROVED,
    "rejected": PurchaseOrderStatus.REJECTED,
    "reject": PurchaseOrderStatus.REJECTED,
    "needs_review": PurchaseOrderStatus.NEEDS_REVIEW,
    "needs review": PurchaseOrderStatus.NEEDS_REVIEW,
    "needsreview": PurchaseOrderStatus.NEEDS_REVIEW,
}


def resolve_approval_status(raw: str) -> PurchaseOrderStatus:
    key = raw.strip().lower().replace("-", "_")
    if key in _STATUS_ALIASES:
        return _STATUS_ALIASES[key]
    try:
        return PurchaseOrderStatus(raw.strip().upper())
    except ValueError as e:
        raise ValueError(
            f"Invalid approval status '{raw}'. Use Approved, Reject, or Needs Review."
        ) from e


class PurchaseOrderNotFoundError(Exception):
    """No PO exists for the given request_id."""


async def approve_purchase_order(
    session: AsyncSession,
    request_id: str,
    body: OrderApproveBody,
) -> OrderApproveResponse:
    result = await session.execute(
        select(PurchaseOrder).where(PurchaseOrder.request_id == request_id).limit(1)
    )
    po = result.scalar_one_or_none()
    if po is None:
        raise PurchaseOrderNotFoundError(f"No purchase order for request_id={request_id}")

    new_status = resolve_approval_status(body.status)
    po.status = new_status
    po.approved_by = body.approved_by
    po.updated_at = body.approved_at or datetime.now(UTC)

    event_type = {
        PurchaseOrderStatus.APPROVED: "APPROVED",
        PurchaseOrderStatus.REJECTED: "REJECTED",
        PurchaseOrderStatus.NEEDS_REVIEW: "NEEDS_REVIEW",
    }.get(new_status, "PO_STATUS_UPDATED")

    session.add(
        ProcurementLog(
            event_type=event_type,
            event_source="orders.approve",
            message=f"PO {po.id} ({request_id}) -> {new_status.value}",
            payload={
                "purchase_order_id": po.id,
                "request_id": request_id,
                "status": new_status.value,
                "approved_by": body.approved_by,
            },
            severity=LogSeverity.INFO,
        )
    )
    await session.commit()
    await session.refresh(po)

    logger.info("PO %s (%s) status set to %s", po.id, request_id, new_status.value)

    return OrderApproveResponse(
        purchase_order_id=po.id,
        request_id=request_id,
        status=po.status,
        approved_by=po.approved_by,
        pdf_path=po.pdf_path,
        total_amount=po.total_amount,
        currency=po.currency,
    )
