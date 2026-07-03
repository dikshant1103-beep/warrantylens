"""sprint 3: AI outputs (transcripts, detections, ocr, vlm, embeddings)

Revision ID: 0003_ai_outputs
Revises: 0002_claims_evidence
Create Date: 2026-06-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_ai_outputs"
down_revision: Union[str, None] = "0002_claims_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ocr_field_type = postgresql.ENUM(
    "vin", "serial", "label", "other", name="ocr_field_type", create_type=False
)
UUID = postgresql.UUID(as_uuid=True)


def _ts():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def _fk_tenant():
    return sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)


def _fk_claim():
    return sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    # add 'skipped' to existing job_status enum
    op.execute("ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'skipped'")
    ocr_field_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "transcripts",
        sa.Column("id", UUID, primary_key=True),
        _fk_tenant(), _fk_claim(),
        sa.Column("media_asset_id", UUID, sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("segments", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_version", sa.String(100), nullable=True),
        *_ts(),
    )
    op.create_index("ix_transcripts_tenant_id", "transcripts", ["tenant_id"])
    op.create_index("ix_transcripts_claim_id", "transcripts", ["claim_id"])

    op.create_table(
        "detections",
        sa.Column("id", UUID, primary_key=True),
        _fk_tenant(), _fk_claim(),
        sa.Column("frame_id", UUID, sa.ForeignKey("frames.id", ondelete="CASCADE"), nullable=True),
        sa.Column("media_asset_id", UUID, sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("component_label", sa.String(100), nullable=True),
        sa.Column("defect_label", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bbox", postgresql.JSONB(), nullable=True),
        sa.Column("severity", sa.Float(), nullable=True),
        *_ts(),
    )
    op.create_index("ix_detections_tenant_id", "detections", ["tenant_id"])
    op.create_index("ix_detections_claim_id", "detections", ["claim_id"])
    op.create_index("ix_detections_defect_label", "detections", ["defect_label"])

    op.create_table(
        "ocr_results",
        sa.Column("id", UUID, primary_key=True),
        _fk_tenant(), _fk_claim(),
        sa.Column("frame_id", UUID, sa.ForeignKey("frames.id", ondelete="CASCADE"), nullable=True),
        sa.Column("media_asset_id", UUID, sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("field_type", ocr_field_type, nullable=False, server_default="other"),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.String(255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bbox", postgresql.JSONB(), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        *_ts(),
    )
    op.create_index("ix_ocr_results_tenant_id", "ocr_results", ["tenant_id"])
    op.create_index("ix_ocr_results_claim_id", "ocr_results", ["claim_id"])

    op.create_table(
        "vlm_analyses",
        sa.Column("id", UUID, primary_key=True),
        _fk_tenant(), _fk_claim(),
        sa.Column("frame_id", UUID, sa.ForeignKey("frames.id", ondelete="CASCADE"), nullable=True),
        sa.Column("media_asset_id", UUID, sa.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("findings", postgresql.JSONB(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        *_ts(),
    )
    op.create_index("ix_vlm_analyses_tenant_id", "vlm_analyses", ["tenant_id"])
    op.create_index("ix_vlm_analyses_claim_id", "vlm_analyses", ["claim_id"])

    op.create_table(
        "embeddings_index",
        sa.Column("id", UUID, primary_key=True),
        _fk_tenant(), _fk_claim(),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("qdrant_point_id", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=True),
        *_ts(),
    )
    op.create_index("ix_embeddings_index_tenant_id", "embeddings_index", ["tenant_id"])
    op.create_index("ix_embeddings_index_claim_id", "embeddings_index", ["claim_id"])


def downgrade() -> None:
    op.drop_table("embeddings_index")
    op.drop_table("vlm_analyses")
    op.drop_table("ocr_results")
    op.drop_table("detections")
    op.drop_table("transcripts")
    ocr_field_type.drop(op.get_bind(), checkfirst=True)
    # Note: removing an enum value (job_status 'skipped') is non-trivial in PG; left in place.
