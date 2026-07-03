import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.db.models.enums import MediaKind, MediaStatus


class UploadFileSpec(BaseModel):
    filename: str
    content_type: str
    kind: MediaKind
    size: int | None = None

    @field_validator("content_type")
    @classmethod
    def _allowed_type(cls, v: str) -> str:
        if v not in settings.allowed_upload_types:
            raise ValueError(
                f"Unsupported content_type '{v}'. Allowed: "
                f"{', '.join(settings.allowed_upload_types)}"
            )
        return v

    @model_validator(mode="after")
    def _max_size(self):
        if self.size is not None and self.size > settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")
        return self


class UploadRequest(BaseModel):
    files: list[UploadFileSpec] = Field(min_length=1, max_length=50)


class UploadSlot(BaseModel):
    asset_id: uuid.UUID
    upload_url: str
    s3_key: str


class UploadResponse(BaseModel):
    uploads: list[UploadSlot]


class UploadComplete(BaseModel):
    sha256: str | None = None


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    claim_id: uuid.UUID
    kind: MediaKind
    content_type: str
    size_bytes: int | None
    sha256: str | None
    duration_s: float | None
    width: int | None
    height: int | None
    status: MediaStatus
    created_at: datetime


class MediaAssetWithUrl(MediaAssetRead):
    url: str | None = None


class FrameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    media_asset_id: uuid.UUID
    timestamp_s: float
    frame_index: int
    is_keyframe: bool
    sharpness: float | None
    url: str | None = None


class EvidenceResponse(BaseModel):
    media: list[MediaAssetWithUrl]
    frames: list[FrameRead]
