"""sprint 2: catalog, claims, media, frames, processing jobs

Revision ID: 0002_claims_evidence
Revises: 0001_initial
Create Date: 2026-06-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_claims_evidence"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

claim_status = postgresql.ENUM(
    "draft", "queued", "processing", "ready_for_review", "reviewed",
    "needs_more_evidence", "failed", name="claim_status", create_type=False,
)
media_kind = postgresql.ENUM("video", "image", name="media_kind", create_type=False)
media_status = postgresql.ENUM(
    "pending", "uploaded", "processed", "rejected", name="media_status",
    create_type=False,
)
job_status = postgresql.ENUM(
    "pending", "running", "succeeded", "failed", name="job_status", create_type=False
)

UUID = postgresql.UUID(as_uuid=True)


def _ts():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (claim_status, media_kind, media_status, job_status):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "components",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("parent_id", UUID, sa.ForeignKey("components.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_components_tenant_code"),
    )
    op.create_index("ix_components_tenant_id", "components", ["tenant_id"])

    op.create_table(
        "fraud_indicator_defs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("default_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("severity", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_fraud_indicator_tenant_code"),
    )
    op.create_index("ix_fraud_indicator_defs_tenant_id", "fraud_indicator_defs", ["tenant_id"])

    op.create_table(
        "inspection_templates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("component_id", UUID, sa.ForeignKey("components.id", ondelete="SET NULL"), nullable=True),
        sa.Column("required_views", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("required_evidence", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.create_index("ix_inspection_templates_tenant_id", "inspection_templates", ["tenant_id"])

    op.create_table(
        "claims",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_number", sa.String(40), nullable=False),
        sa.Column("vin", sa.String(17), nullable=True),
        sa.Column("status", claim_status, nullable=False, server_default="draft"),
        sa.Column("component_id", UUID, sa.ForeignKey("components.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_id", UUID, sa.ForeignKey("inspection_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("claim_reason", sa.Text(), nullable=True),
        sa.Column("mechanic_narrative", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_reviewer_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("completeness_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
    )
    op.create_index("ix_claims_tenant_id", "claims", ["tenant_id"])
    op.create_index("ix_claims_claim_number", "claims", ["claim_number"], unique=True)
    op.create_index("ix_claims_vin", "claims", ["vin"])
    op.create_index("ix_claims_status", "claims", ["status"])
    op.create_index("ix_claims_tenant_status", "claims", ["tenant_id", "status", "created_at"])

    op.create_table(
        "media_assets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", media_kind, nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("duration_s", sa.Numeric(10, 3), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("status", media_status, nullable=False, server_default="pending"),
        sa.Column("uploaded_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_ts(),
    )
    op.create_index("ix_media_assets_tenant_id", "media_assets", ["tenant_id"])
    op.create_index("ix_media_assets_claim_id", "media_assets", ["claim_id"])

    op.create_table(
        "frames",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_asset_id", UUID, sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("timestamp_s", sa.Float(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("is_keyframe", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sharpness", sa.Float(), nullable=True),
        *_ts(),
    )
    op.create_index("ix_frames_tenant_id", "frames", ["tenant_id"])
    op.create_index("ix_frames_claim_id", "frames", ["claim_id"])
    op.create_index("ix_frames_media_asset_id", "frames", ["media_asset_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("celery_task_id", sa.String(155), nullable=True),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        *_ts(),
    )
    op.create_index("ix_processing_jobs_claim_id", "processing_jobs", ["claim_id"])


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_table("frames")
    op.drop_table("media_assets")
    op.drop_table("claims")
    op.drop_table("inspection_templates")
    op.drop_table("fraud_indicator_defs")
    op.drop_table("components")
    bind = op.get_bind()
    for enum in (job_status, media_status, media_kind, claim_status):
        enum.drop(bind, checkfirst=True)
