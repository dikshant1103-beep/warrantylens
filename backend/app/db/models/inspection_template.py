from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin


class InspectionTemplate(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Defines the required shot list / evidence for inspecting a component.

    required_views: e.g. ["front", "left", "right", "rear", "serial_closeup"]
    required_evidence: e.g. {"vin": true, "audio_narration": true, "min_images": 4}
    """

    __tablename__ = "inspection_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("components.id", ondelete="SET NULL"), nullable=True
    )
    required_views: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    required_evidence: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
