"""Fine-tune YOLOv11n on CarDD (real car-damage images) for the WarrantyLens
vision pipeline. Memory-safe for a 4 GB GPU with automatic batch fallback.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vision" / "CarDD_yolo" / "cardd.yaml"
OUT = ROOT / "models"
OUT.mkdir(exist_ok=True)

# (device, batch, imgsz) attempts — shrink on OOM.
ATTEMPTS = [(0, 8, 512), (0, 4, 448), ("cpu", 16, 512)]
EPOCHS = 40


def main() -> None:
    last_err = None
    for device, batch, imgsz in ATTEMPTS:
        try:
            print(f"\n=== Training: device={device} batch={batch} imgsz={imgsz} ===")
            model = YOLO("yolo11n.pt")
            results = model.train(
                data=str(DATA), epochs=EPOCHS, imgsz=imgsz, batch=batch,
                device=device, project=str(OUT / "yolo"), name="cardd",
                patience=12, exist_ok=True, verbose=True,
                # CPU fallback: cut epochs so it finishes in reasonable time
                **({"epochs": 15} if device == "cpu" else {}),
            )
            best = OUT / "yolo" / "cardd" / "weights" / "best.pt"
            if best.exists():
                shutil.copy(best, OUT / "ev_defects.pt")
                print(f"\nSaved fine-tuned model -> {OUT/'ev_defects.pt'}")
            # report metrics
            mp = results.results_dict if hasattr(results, "results_dict") else {}
            print("METRICS:", {k: round(float(v), 4) for k, v in mp.items()
                               if isinstance(v, (int, float))})
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            msg = str(exc).lower()
            if "out of memory" in msg or "cuda" in msg:
                print(f"!! attempt failed ({device}/{batch}): {str(exc)[:120]} — retrying smaller")
                import torch
                torch.cuda.empty_cache()
                continue
            raise
    raise RuntimeError(f"All training attempts failed: {last_err}")


if __name__ == "__main__":
    main()
