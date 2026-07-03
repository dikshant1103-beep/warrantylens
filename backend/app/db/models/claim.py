from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import ClaimStatus
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.media import Frame, MediaAsset


class Claim(UUIDMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "claims"

    claim_number: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True, index=True)
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claim_status"),
        default=ClaimStatus.draft,
        nullable=False,
        index=True,
    )

    component_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("components.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspection_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    claim_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    mechanic_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Serial-number lifecycle: the defective part claimed (removed) and its
    # replacement. Drive anti-swap-and-sell fraud checks.
    removed_serial: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replacement_serial: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    completeness_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    media_assets: Mapped[list[MediaAsset]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    frames: Mapped[list[Frame]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
