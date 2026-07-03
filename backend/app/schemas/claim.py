import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.enums import ClaimStatus


def _normalize_vin(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().upper()
    return v or None


class ClaimCreate(BaseModel):
    vin: str | None = Field(default=None, max_length=17)
    component_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    claim_reason: str | None = None
    mechanic_narrative: str | None = None
    removed_serial: str | None = Field(default=None, max_length=100)
    replacement_serial: str | None = Field(default=None, max_length=100)

    _vin = field_validator("vin")(_normalize_vin)


class ClaimUpdate(BaseModel):
    vin: str | None = Field(default=None, max_length=17)
    component_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    claim_reason: str | None = None
    mechanic_narrative: str | None = None
    removed_serial: str | None = Field(default=None, max_length=100)
    replacement_serial: str | None = Field(default=None, max_length=100)

    _vin = field_validator("vin")(_normalize_vin)


class ClaimAssign(BaseModel):
    reviewer_id: uuid.UUID


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    claim_number: str
    vin: str | None
    status: ClaimStatus
    component_id: uuid.UUID | None
    template_id: uuid.UUID | None
    claim_reason: str | None
    mechanic_narrative: str | None
    removed_serial: str | None
    replacement_serial: str | None
    created_by_user_id: uuid.UUID
    assigned_reviewer_id: uuid.UUID | None
    completeness_score: float | None
    risk_score: float | None
    submitted_at: datetime | None
    processed_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime


class ClaimList(BaseModel):
    items: list[ClaimRead]
    page: int
    size: int
    total: int


class StageStatus(BaseModel):
    stage: str
    status: str
    error: str | None = None


class ClaimStatusResponse(BaseModel):
    claim_id: uuid.UUID
    status: ClaimStatus
    processing_error: str | None
    stages: list[StageStatus]
