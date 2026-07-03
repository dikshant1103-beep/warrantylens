from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Vehicle(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """Vehicle master record — the start of the per-VIN 'digital passport'.

    telemetry_profile is the simulator's ground-truth label
    (normal | abuse | latent_defect | water_impact).
    """

    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("tenant_id", "vin", name="uq_vehicles_tenant_vin"),)

    vin: Mapped[str] = mapped_column(String(17), nullable=False, index=True)
    make: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    telemetry_profile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    manufactured_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class TelemetrySnapshot(UUIDMixin, TenantMixin, TimestampMixin, Base):
    """One day of aggregated non-battery telemetry for a vehicle.

    (Production would use a time-series DB for raw high-frequency data; we store
    daily aggregates, which is enough for warranty-history analysis.)
    """

    __tablename__ = "telemetry_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "vin", "day", name="uq_telemetry_vin_day"),
    )

    vin: Mapped[str] = mapped_column(String(17), nullable=False, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)

    distance_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    odometer_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ambient_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    motor_temp_avg_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    motor_temp_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    controller_temp_avg_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    controller_temp_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    overcurrent_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    harsh_accel_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    harsh_brake_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    water_ingress_trip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impact_event: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fault_codes: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
