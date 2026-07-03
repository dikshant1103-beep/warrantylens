"""sprint 4: completeness, risk, reports, reviews

Revision ID: 0004_scoring_review
Revises: 0003_ai_outputs
Create Date: 2026-06-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_scoring_review"
down_revision: Union[str, None] = "0003_ai_outputs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

review_decision = postgresql.ENUM(
    "approved", "rejected", "needs_more_evidence", "escalated",
    name="review_decision", create_type=False,
)
UUID = postgresql.UUID(as_uuid=True)


def _ts():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def upgrade() -> None:
    review_decision.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "completeness_checks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", UUID, sa.ForeignKey("inspection_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("required", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("present", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("missing", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_completeness_checks_tenant_id", "completeness_checks", ["tenant_id"])
    op.create_index("ix_completeness_checks_claim_id", "completeness_checks", ["claim_id"])

    op.create_table(
        "risk_assessments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("factors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        *_ts(),
    )
    op.create_index("ix_risk_assessments_tenant_id", "risk_assessments", ["tenant_id"])
    op.create_index("ix_risk_assessments_claim_id", "risk_assessments", ["claim_id"])

    op.create_table(
        "reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("s3_key_pdf", sa.String(512), nullable=True),
        sa.Column("s3_key_html", sa.String(512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_ts(),
    )
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])
    op.create_index("ix_reports_claim_id", "reports", ["claim_id"])

    op.create_table(
        "reviews",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", review_decision, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("overrides", postgresql.JSONB(), nullable=True),
        *_ts(),
    )
    op.create_index("ix_reviews_tenant_id", "reviews", ["tenant_id"])
    op.create_index("ix_reviews_claim_id", "reviews", ["claim_id"])


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("reports")
    op.drop_table("risk_assessments")
    op.drop_table("completeness_checks")
    review_decision.drop(op.get_bind(), checkfirst=True)
