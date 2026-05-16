from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.enums import LogSeverity


class ProcurementLog(Base):
    __tablename__ = "procurement_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_source: Mapped[str | None] = mapped_column(String(128), index=True)
    message: Mapped[str | None] = mapped_column(String(2000))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    severity: Mapped[LogSeverity] = mapped_column(
        Enum(LogSeverity, name="procurement_log_severity", native_enum=False, length=16),
        nullable=False,
        default=LogSeverity.INFO,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
