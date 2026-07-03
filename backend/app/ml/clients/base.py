from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ASRResult:
    full_text: str = ""
    language: str | None = None
    segments: list[dict] = field(default_factory=list)
    model_version: str | None = None


@dataclass
class DetectionResult:
    component_label: str | None = None
    defect_label: str | None = None
    confidence: float = 0.0
    bbox: dict | None = None  # {x,y,w,h} normalized 0..1
    severity: float | None = None


@dataclass
class OcrToken:
    text: str
    confidence: float = 0.0
    bbox: dict | None = None


@dataclass
class VLMResult:
    description: str = ""
    findings: dict | None = None
    raw_response: dict | None = None
    model_version: str | None = None
