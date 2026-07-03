from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "WarrantyLens"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = (
        "postgresql+asyncpg://warrantylens:warrantylens@localhost:5432/warrantylens"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    jwt_secret: str = "dev-insecure-change-me-please-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS (NoDecode: parse comma-separated env string ourselves, not as JSON)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Seed
    seed_tenant_name: str = "Demo EV Service"
    seed_tenant_slug: str = "demo"
    seed_admin_email: str = "admin@demo.warrantylens.io"
    seed_admin_password: str = "Admin12345!"

    # S3
    s3_endpoint_url: str = "http://localhost:9000"
    # Endpoint baked into presigned URLs handed to the browser. Inside Docker the
    # internal endpoint is http://minio:9000 (unreachable from the host browser),
    # so presigning must use a host-reachable URL like http://localhost:9000.
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "warrantylens"
    s3_region: str = "us-east-1"

    # --- AI pipeline (Sprint 3) ---
    # Master switch. When false, AI stages are cleanly SKIPPED (no heavy deps needed)
    # so the app runs end-to-end without models installed.
    ai_enabled: bool = False

    # VLM (Qwen2.5-VL via Ollama — benchmarked on GTX 1650 Ti, ~67s/img warm)
    vlm_enabled: bool = False
    ollama_url: str = "http://localhost:11434"
    vlm_model: str = "qwen2.5vl:7b"
    vlm_max_keyframes: int = 10          # cost cap (fits ~30-min budget on CPU)
    vlm_prompt_version: str = "inspection-v1"
    vlm_timeout_s: int = 600

    # ASR (Whisper)
    asr_enabled: bool = False
    whisper_model: str = "base"          # base/small/medium/large-v3
    whisper_compute_type: str = "int8"

    # Detection (YOLOv11)
    yolo_enabled: bool = False
    yolo_weights: str = "yolo11n.pt"     # swap to a fine-tuned EV-defect checkpoint
    yolo_conf: float = 0.25

    # OCR (PaddleOCR) — VIN/serial parsing always runs even if OCR engine off
    ocr_enabled: bool = False
    ocr_lang: str = "en"

    # Embeddings (BGE-M3) + Qdrant
    embeddings_enabled: bool = False
    embed_model: str = "BAAI/bge-m3"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_prefix: str = "wl"

    # --- Hardening (Sprint 5) ---
    security_headers_enabled: bool = True
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120        # general API budget per client
    auth_rate_limit_per_minute: int = 10    # stricter on auth endpoints
    max_upload_mb: int = 500                # per-file evidence cap
    allowed_upload_types: Annotated[list[str], NoDecode] = [
        "video/mp4", "video/quicktime", "video/x-matroska", "video/webm",
        "image/jpeg", "image/png", "image/webp", "image/heic",
    ]

    @field_validator("allowed_upload_types", mode="before")
    @classmethod
    def _split_types(cls, v: object) -> object:
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v

    def assert_production_safe(self) -> list[str]:
        """Return a list of misconfigurations that must be fixed in production."""
        problems: list[str] = []
        if "change-me" in self.jwt_secret or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET is default/weak")
        if self.debug:
            problems.append("DEBUG must be false in production")
        if self.s3_secret_key in ("minioadmin", "") or self.s3_access_key == "minioadmin":
            problems.append("Default S3 credentials in use")
        return problems

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
