"""battery health report (BatteryOS integration)

Revision ID: 0006_battery_report
Revises: 0005_serial_lifecycle
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_battery_report"
down_revision: Union[str, None] = "0005_serial_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "battery_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="BatteryOS"),
        sa.Column("schema_version", sa.String(20), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vin", sa.String(17), nullable=True),
        sa.Column("pack_id", sa.String(100), nullable=True),
        sa.Column("chemistry", sa.String(20), nullable=True),
        sa.Column("soh_percent", sa.Float(), nullable=True),
        sa.Column("rul_cycles", sa.Float(), nullable=True),
        sa.Column("rul_ci_low", sa.Float(), nullable=True),
        sa.Column("rul_ci_high", sa.Float(), nullable=True),
        sa.Column("capacity_fade_percent", sa.Float(), nullable=True),
        sa.Column("charging", postgresql.JSONB(), nullable=True),
        sa.Column("faults", postgresql.JSONB(), nullable=True),
        sa.Column("abuse_indicators", postgresql.JSONB(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("warranty_leaning", sa.String(30), nullable=True),
        sa.Column("assessment_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_battery_reports_tenant_id", "battery_reports", ["tenant_id"])
    op.create_index("ix_battery_reports_claim_id", "battery_reports", ["claim_id"])


def downgrade() -> None:
    op.drop_table("battery_reports")
