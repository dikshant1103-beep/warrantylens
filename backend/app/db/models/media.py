from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import MediaKind, MediaStatus
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.claim import Claim


class MediaAsset(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A raw uploaded video or image."""

    __tablename__ = "media_assets"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[MediaKind] = mapped_column(Enum(MediaKind, name="media_kind"), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[MediaStatus] = mapped_column(
        Enum(MediaStatus, name="media_status"), default=MediaStatus.pending, nullable=False
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    claim: Mapped[Claim] = relationship(back_populates="media_assets")
    frames: Mapped[list[Frame]] = relationship(
        back_populates="media_asset", cascade="all, delete-orphan"
    )


class Frame(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A frame extracted from a video media asset."""

    __tablename__ = "frames"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    timestamp_s: Mapped[float] = mapped_column(Float, nullable=False)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_keyframe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sharpness: Mapped[float | None] = mapped_column(Float, nullable=True)

    claim: Mapped[Claim] = relationship(back_populates="frames")
    media_asset: Mapped[MediaAsset] = relationship(back_populates="frames")
