import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import OcrFieldType


class TranscriptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    media_asset_id: uuid.UUID | None
    language: str | None
    full_text: str
    segments: list
    model_version: str | None
    created_at: datetime


class DetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    frame_id: uuid.UUID | None
    media_asset_id: uuid.UUID | None
    component_label: str | None
    defect_label: str | None
    confidence: float
    bbox: dict | None
    severity: float | None
    model_version: str | None


class OcrResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    frame_id: uuid.UUID | None
    field_type: OcrFieldType
    raw_text: str | None
    normalized_value: str | None
    confidence: float
    model_version: str | None


class VlmAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    frame_id: uuid.UUID | None
    prompt_version: str | None
    model_version: str | None
    description: str | None
    findings: dict | None
    created_at: datetime
