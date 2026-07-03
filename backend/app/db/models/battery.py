from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin


class BatteryReport(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A Battery Health Report (BHR) imported from BatteryOS and attached to a
    claim. WarrantyLens only READS this contract — BatteryOS produces it. Used to
    bring battery health/RUL/abuse context into the warranty assessment.
    """

    __tablename__ = "battery_reports"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(String(50), default="BatteryOS", nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)
    pack_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chemistry: Mapped[str | None] = mapped_column(String(20), nullable=True)

    soh_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    rul_cycles: Mapped[float | None] = mapped_column(Float, nullable=True)
    rul_ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    rul_ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacity_fade_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    charging: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    faults: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    abuse_indicators: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Advisory leaning derived from battery signals:
    # supports_warranty | inconclusive | suggests_misuse
    warranty_leaning: Mapped[str | None] = mapped_column(String(30), nullable=True)
    assessment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
