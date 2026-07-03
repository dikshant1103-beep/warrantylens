"""Battery Health Report (BHR) — the contract WarrantyLens reads from BatteryOS.

Lenient on input (BatteryOS may omit fields); strict on what we expose.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BHRRul(BaseModel):
    cycles: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    km: float | None = None
    confidence: float | None = None


class BHRFault(BaseModel):
    code: str | None = None
    desc: str | None = None
    severity: str | None = None
    ts: str | None = None


class BHRVehicle(BaseModel):
    vin: str | None = None
    pack_id: str | None = None


class BatteryHealthReport(BaseModel):
    """Inbound BHR file payload."""

    model_config = ConfigDict(extra="allow")

    schema_version: str | None = None
    source: str = "BatteryOS"
    generated_at: datetime | None = None
    vehicle: BHRVehicle = Field(default_factory=BHRVehicle)
    chemistry: str | None = None
    soh_percent: float | None = None
    rul: BHRRul = Field(default_factory=BHRRul)
    capacity_fade_percent: float | None = None
    charging: dict | None = None
    faults: list[BHRFault] = Field(default_factory=list)
    abuse_indicators: list[str] = Field(default_factory=list)


class BatteryReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    generated_at: datetime | None
    vin: str | None
    pack_id: str | None
    chemistry: str | None
    soh_percent: float | None
    rul_cycles: float | None
    rul_ci_low: float | None
    rul_ci_high: float | None
    capacity_fade_percent: float | None
    charging: dict | None
    faults: list | None
    abuse_indicators: list | None
    warranty_leaning: str | None
    assessment_note: str | None
    created_at: datetime
