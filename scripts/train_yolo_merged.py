"""Fine-tune YOLOv11n on the merged dataset (CarDD + rust + corrosion).
Memory-safe for a 4 GB GPU with automatic batch fallback. Saves ev_defects_v2.pt.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vision" / "merged_yolo" / "merged.yaml"
OUT = ROOT / "models"
OUT.mkdir(exist_ok=True)

ATTEMPTS = [(0, 8, 512), (0, 4, 448), ("cpu", 16, 512)]
EPOCHS = 50


def main() -> None:
    last = None
    for device, batch, imgsz in ATTEMPTS:
        try:
            print(f"\n=== device={device} batch={batch} imgsz={imgsz} ===")
            model = YOLO("yolo11n.pt")
            results = model.train(
                data=str(DATA), epochs=EPOCHS if device != "cpu" else 15,
                imgsz=imgsz, batch=batch, device=device,
                project=str(OUT / "yolo"), name="merged", exist_ok=True,
                patience=15, verbose=True,
            )
            best = OUT / "yolo" / "merged" / "weights" / "best.pt"
            if best.exists():
                shutil.copy(best, OUT / "ev_defects_v2.pt")
                print(f"\nSaved -> {OUT/'ev_defects_v2.pt'}")
            mp = getattr(results, "results_dict", {})
            print("METRICS:", {k: round(float(v), 4) for k, v in mp.items()
                               if isinstance(v, (int, float))})
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            if "out of memory" in str(exc).lower() or "cuda" in str(exc).lower():
                import torch
                torch.cuda.empty_cache()
                print(f"!! retry smaller ({device}/{batch}): {str(exc)[:100]}")
                continue
            raise
    raise RuntimeError(f"all attempts failed: {last}")


if __name__ == "__main__":
    main()
