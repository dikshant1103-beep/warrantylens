import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import ReviewDecision


class ReviewCreate(BaseModel):
    decision: ReviewDecision
    notes: str | None = None
    overrides: dict | None = None


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    claim_id: uuid.UUID
    reviewer_id: uuid.UUID
    decision: ReviewDecision
    notes: str | None
    overrides: dict | None
    created_at: datetime
