"""Whisper ASR via faster-whisper. Multilingual (English + Hindi/Hinglish)."""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.clients.base import ASRResult

log = get_logger(__name__)
_model = None


class WhisperASR:
    def available(self) -> bool:
        if not (settings.ai_enabled and settings.asr_enabled):
            return False
        try:
            import faster_whisper  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            log.warning("asr unavailable: faster-whisper not installed")
            return False

    def _load(self):
        global _model
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(
                settings.whisper_model, compute_type=settings.whisper_compute_type
            )
        return _model

    def transcribe(self, audio_path: str) -> ASRResult:
        model = self._load()
        segments, info = model.transcribe(audio_path, vad_filter=True)
        segs, texts = [], []
        for s in segments:
            segs.append({"start": s.start, "end": s.end, "text": s.text})
            texts.append(s.text)
        return ASRResult(
            full_text=" ".join(t.strip() for t in texts).strip(),
            language=getattr(info, "language", None),
            segments=segs,
            model_version=f"whisper-{settings.whisper_model}",
        )


def get_asr() -> WhisperASR | None:
    c = WhisperASR()
    return c if c.available() else None
