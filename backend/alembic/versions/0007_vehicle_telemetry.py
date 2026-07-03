"""vehicle master + non-battery telemetry snapshots

Revision ID: 0007_vehicle_telemetry
Revises: 0006_battery_report
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_vehicle_telemetry"
down_revision: Union[str, None] = "0006_battery_report"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def _ts():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vin", sa.String(17), nullable=False),
        sa.Column("make", sa.String(80), nullable=True),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("telemetry_profile", sa.String(30), nullable=True),
        sa.Column("manufactured_at", sa.Date(), nullable=True),
        *_ts(),
        sa.UniqueConstraint("tenant_id", "vin", name="uq_vehicles_tenant_vin"),
    )
    op.create_index("ix_vehicles_tenant_id", "vehicles", ["tenant_id"])
    op.create_index("ix_vehicles_vin", "vehicles", ["vin"])

    op.create_table(
        "telemetry_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vin", sa.String(17), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False, server_default="0"),
        sa.Column("odometer_km", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ambient_temp_c", sa.Float(), nullable=True),
        sa.Column("motor_temp_avg_c", sa.Float(), nullable=True),
        sa.Column("motor_temp_max_c", sa.Float(), nullable=True),
        sa.Column("controller_temp_avg_c", sa.Float(), nullable=True),
        sa.Column("controller_temp_max_c", sa.Float(), nullable=True),
        sa.Column("overcurrent_events", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("harsh_accel_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("harsh_brake_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("water_ingress_trip", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("impact_event", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fault_codes", postgresql.JSONB(), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.UniqueConstraint("tenant_id", "vin", "day", name="uq_telemetry_vin_day"),
    )
    op.create_index("ix_telemetry_snapshots_tenant_id", "telemetry_snapshots", ["tenant_id"])
    op.create_index("ix_telemetry_snapshots_vin", "telemetry_snapshots", ["vin"])


def downgrade() -> None:
    op.drop_table("telemetry_snapshots")
    op.drop_table("vehicles")
