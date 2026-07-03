"""OCR via Tesseract (pytesseract). Chosen over PaddleOCR for clean, reliable
CPU installation (no torch/numpy ABI conflicts). VIN/serial parsing lives in
postprocess.vin and runs regardless of whether the OCR engine is installed."""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.clients.base import OcrToken

log = get_logger(__name__)
_MIN_CONF = 20.0  # drop very low-confidence tesseract words
# --psm 6: treat the image as a single uniform block of text (good for labels/VIN plates)
_TESS_CONFIG = "--oem 3 --psm 6"


class TesseractOCR:
    def available(self) -> bool:
        if not (settings.ai_enabled and settings.ocr_enabled):
            return False
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("ocr unavailable: tesseract not installed", error=str(exc))
            return False

    def read(self, image_path: str) -> list[OcrToken]:
        import pytesseract
        from PIL import Image

        # Tesseract lang codes: "en" -> "eng".
        lang = "eng" if settings.ocr_lang in ("en", "eng") else settings.ocr_lang
        with Image.open(image_path) as img:
            data = pytesseract.image_to_data(
                img, lang=lang, config=_TESS_CONFIG,
                output_type=pytesseract.Output.DICT,
            )

        tokens: list[OcrToken] = []
        for i, text in enumerate(data["text"]):
            text = (text or "").strip()
            if not text:
                continue
            try:
                conf = float(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1.0
            if conf < _MIN_CONF:
                continue
            tokens.append(
                OcrToken(
                    text=text,
                    confidence=conf / 100.0,
                    bbox={
                        "x": data["left"][i], "y": data["top"][i],
                        "w": data["width"][i], "h": data["height"][i],
                    },
                )
            )
        return tokens


def get_ocr() -> TesseractOCR | None:
    c = TesseractOCR()
    return c if c.available() else None
