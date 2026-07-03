import uuid

from pydantic import BaseModel, ConfigDict, Field


# --- Component ---------------------------------------------------------------
class ComponentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = None
    parent_id: uuid.UUID | None = None


class ComponentUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None


class ComponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    category: str | None
    parent_id: uuid.UUID | None
    is_active: bool


# --- Inspection template -----------------------------------------------------
class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    component_id: uuid.UUID | None = None
    required_views: list[str] = []
    required_evidence: dict = {}


class TemplateUpdate(BaseModel):
    name: str | None = None
    required_views: list[str] | None = None
    required_evidence: dict | None = None
    is_active: bool | None = None


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: int
    component_id: uuid.UUID | None
    required_views: list[str]
    required_evidence: dict
    is_active: bool


# --- Risk indicator ----------------------------------------------------------
class FraudIndicatorCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=255)
    default_weight: float = 1.0
    severity: str = "medium"


class FraudIndicatorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    label: str
    default_weight: float
    severity: str
    is_active: bool
