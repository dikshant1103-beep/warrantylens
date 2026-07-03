from __future__ import annotations

import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import OcrFieldType
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Transcript(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Whisper ASR output for an audio/video asset."""

    __tablename__ = "transcripts"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    full_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    segments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Detection(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """One detected component/defect on a frame (YOLOv11)."""

    __tablename__ = "detections"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frame_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frames.id", ondelete="CASCADE"), nullable=True
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True
    )
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    component_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    defect_label: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {x,y,w,h} normalized
    severity: Mapped[float | None] = mapped_column(Float, nullable=True)


class OcrResult(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """OCR-extracted VIN / serial / label (PaddleOCR + parsing)."""

    __tablename__ = "ocr_results"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frame_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frames.id", ondelete="CASCADE"), nullable=True
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True
    )
    field_type: Mapped[OcrFieldType] = mapped_column(
        Enum(OcrFieldType, name="ocr_field_type"), default=OcrFieldType.other, nullable=False
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)


class VlmAnalysis(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Qwen2.5-VL grounded description + structured findings for a keyframe."""

    __tablename__ = "vlm_analyses"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frame_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frames.id", ondelete="CASCADE"), nullable=True
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True
    )
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class EmbeddingIndex(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Mirror of a vector stored in Qdrant (for traceability/cleanup)."""

    __tablename__ = "embeddings_index"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qdrant_point_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
