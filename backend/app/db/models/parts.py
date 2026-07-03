from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import PartEventType
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin


class VehiclePart(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Registry of components known to belong to a vehicle (by VIN + serial).

    This is the backbone of anti-'swap-and-sell' fraud detection: a warranty
    claim's removed part must be a serial registered to THAT vehicle, and once
    removed it can't be claimed again.
    """

    __tablename__ = "vehicle_parts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "serial", name="uq_vehicle_parts_tenant_serial"),
    )

    vin: Mapped[str] = mapped_column(String(17), nullable=False, index=True)
    component_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    removed_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL"), nullable=True
    )


class PartEvent(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Append-only lifecycle log: which physical part (serial) was registered,
    claimed/removed, or installed — on which VIN, by which claim."""

    __tablename__ = "part_events"

    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=True, index=True
    )
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True, index=True)
    component_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    event_type: Mapped[PartEventType] = mapped_column(
        Enum(PartEventType, name="part_event_type"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
