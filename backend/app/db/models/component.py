from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Component(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Inspectable EV component (e.g. charging_port, motor_housing)."""

    __tablename__ = "components"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_components_tenant_code"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("components.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FraudIndicatorDef(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Tenant-tunable definition of a risk indicator. Never named 'fraud' to the
    end user — these drive advisory risk factors, not accusations."""

    __tablename__ = "fraud_indicator_defs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_fraud_indicator_tenant_code"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    default_weight: Mapped[float] = mapped_column(default=1.0, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
