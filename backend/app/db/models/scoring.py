from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import ReviewDecision
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin


class CompletenessCheck(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Evidence completeness vs the inspection template."""

    __tablename__ = "completeness_checks"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspection_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    required: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    present: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    missing: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)


class RiskAssessment(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Explainable, advisory risk score. factors decompose the score into named,
    evidence-linked contributions. NEVER a fraud determination."""

    __tablename__ = "risk_assessments"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    factors: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Report(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Generated inspection report (regenerable, versioned)."""

    __tablename__ = "reports"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    s3_key_pdf: Mapped[str | None] = mapped_column(String(512), nullable=True)
    s3_key_html: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Review(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """A human reviewer's decision on a claim. System never writes here."""

    __tablename__ = "reviews"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="review_decision"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
