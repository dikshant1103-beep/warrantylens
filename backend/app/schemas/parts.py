import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PartRegister(BaseModel):
    vin: str = Field(min_length=1, max_length=17)
    serial: str = Field(min_length=1, max_length=100)
    component_code: str | None = None


class VehiclePartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vin: str
    serial: str
    component_code: str | None
    is_active: bool
    created_at: datetime


class PartEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    claim_id: uuid.UUID | None
    vin: str | None
    serial: str | None
    component_code: str | None
    event_type: str
    note: str | None
    created_at: datetime
