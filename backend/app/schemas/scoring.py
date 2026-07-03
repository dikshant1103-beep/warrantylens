import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompletenessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    template_id: uuid.UUID | None
    required: dict
    present: dict
    missing: list
    score: float
    created_at: datetime


class RiskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    score: float
    factors: list
    rationale: str | None
    model_version: str | None
    created_at: datetime


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    summary: str | None
    payload: dict
    created_at: datetime
    pdf_url: str | None = None
    html_url: str | None = None
