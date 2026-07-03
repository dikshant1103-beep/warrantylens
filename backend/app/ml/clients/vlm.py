"""Vision-Language Model client. Default: Qwen2.5-VL via Ollama (benchmarked on
GTX 1650 Ti, CPU-bound ~67s/img warm). Swappable: a vLLM-on-cloud impl can drop
in behind the same interface for production demos."""
from __future__ import annotations

import base64
import json

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.clients.base import VLMResult

log = get_logger(__name__)


class OllamaVLM:
    provider = "ollama"

    def __init__(self) -> None:
        self.url = settings.ollama_url.rstrip("/")
        self.model = settings.vlm_model

    def available(self) -> bool:
        if not (settings.ai_enabled and settings.vlm_enabled):
            return False
        try:
            import httpx

            r = httpx.get(f"{self.url}/api/version", timeout=5)
            return r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            log.warning("vlm unavailable", error=str(exc))
            return False

    def describe_image(self, image_bytes: bytes, prompt: str) -> VLMResult:
        import httpx

        img_b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 400},
        }
        r = httpx.post(
            f"{self.url}/api/generate", json=payload, timeout=settings.vlm_timeout_s
        )
        r.raise_for_status()
        body = r.json()
        text = body.get("response", "")
        findings = _parse_json(text)
        return VLMResult(
            description=findings.get("notes", text) if findings else text,
            findings=findings,
            raw_response={"response": text},
            model_version=self.model,
        )


def _parse_json(text: str) -> dict | None:
    """Best-effort extraction of a JSON object from the model output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def get_vlm() -> OllamaVLM | None:
    client = OllamaVLM()
    return client if client.available() else None
