"""sprint: serial-number lifecycle (vehicle_parts, part_events, claim serials)

Revision ID: 0005_serial_lifecycle
Revises: 0004_scoring_review
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_serial_lifecycle"
down_revision: Union[str, None] = "0004_scoring_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

part_event_type = postgresql.ENUM(
    "registered", "claimed_removed", "installed", "flagged",
    name="part_event_type", create_type=False,
)
UUID = postgresql.UUID(as_uuid=True)


def _ts():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def upgrade() -> None:
    part_event_type.create(op.get_bind(), checkfirst=True)

    op.add_column("claims", sa.Column("removed_serial", sa.String(100), nullable=True))
    op.add_column("claims", sa.Column("replacement_serial", sa.String(100), nullable=True))

    op.create_table(
        "vehicle_parts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vin", sa.String(17), nullable=False),
        sa.Column("component_code", sa.String(100), nullable=True),
        sa.Column("serial", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("removed_claim_id", UUID, sa.ForeignKey("claims.id", ondelete="SET NULL"), nullable=True),
        *_ts(),
        sa.UniqueConstraint("tenant_id", "serial", name="uq_vehicle_parts_tenant_serial"),
    )
    op.create_index("ix_vehicle_parts_tenant_id", "vehicle_parts", ["tenant_id"])
    op.create_index("ix_vehicle_parts_vin", "vehicle_parts", ["vin"])
    op.create_index("ix_vehicle_parts_serial", "vehicle_parts", ["serial"])

    op.create_table(
        "part_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=True),
        sa.Column("vin", sa.String(17), nullable=True),
        sa.Column("component_code", sa.String(100), nullable=True),
        sa.Column("serial", sa.String(100), nullable=True),
        sa.Column("event_type", part_event_type, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_ts(),
    )
    op.create_index("ix_part_events_tenant_id", "part_events", ["tenant_id"])
    op.create_index("ix_part_events_claim_id", "part_events", ["claim_id"])
    op.create_index("ix_part_events_vin", "part_events", ["vin"])
    op.create_index("ix_part_events_serial", "part_events", ["serial"])


def downgrade() -> None:
    op.drop_table("part_events")
    op.drop_table("vehicle_parts")
    op.drop_column("claims", "replacement_serial")
    op.drop_column("claims", "removed_serial")
    part_event_type.drop(op.get_bind(), checkfirst=True)
