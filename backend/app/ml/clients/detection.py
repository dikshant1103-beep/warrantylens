"""YOLOv11 detection via ultralytics. Default weights are generic (COCO); swap
`yolo_weights` for a fine-tuned EV component/defect checkpoint (see DATA_PLAN)."""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.clients.base import DetectionResult

log = get_logger(__name__)
_model = None

# Class names that represent damage indicators rather than components.
DEFECT_CLASSES = {
    "crack", "scratch", "impact_dent", "dent", "broken", "missing_part",
    "corrosion", "rust", "water_stain", "tamper_mark", "missing_seal",
    "opened_enclosure", "non_standard_mod",
    # CarDD fine-tuned classes:
    "glass shatter", "lamp broken", "tire flat",
}


class YoloDetector:
    def available(self) -> bool:
        if not (settings.ai_enabled and settings.yolo_enabled):
            return False
        try:
            import ultralytics  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            log.warning("detection unavailable: ultralytics not installed")
            return False

    def _load(self):
        global _model
        if _model is None:
            from ultralytics import YOLO

            _model = YOLO(settings.yolo_weights)
        return _model

    def detect(self, image_path: str) -> list[DetectionResult]:
        model = self._load()
        results = model.predict(image_path, conf=settings.yolo_conf, verbose=False)
        out: list[DetectionResult] = []
        for res in results:
            names = res.names
            h, w = res.orig_shape
            for box in res.boxes:
                cls = names[int(box.cls)]
                conf = float(box.conf)
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                bbox = {
                    "x": x1 / w, "y": y1 / h,
                    "w": (x2 - x1) / w, "h": (y2 - y1) / h,
                }
                is_defect = cls.lower() in DEFECT_CLASSES
                area = bbox["w"] * bbox["h"]
                out.append(
                    DetectionResult(
                        component_label=None if is_defect else cls,
                        defect_label=cls if is_defect else None,
                        confidence=conf,
                        bbox=bbox,
                        severity=(conf * min(area * 4, 1.0)) if is_defect else None,
                    )
                )
        return out


def get_detector() -> YoloDetector | None:
    c = YoloDetector()
    return c if c.available() else None
