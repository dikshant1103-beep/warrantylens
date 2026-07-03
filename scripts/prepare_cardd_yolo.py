"""Convert the CarDD FiftyOne dataset (samples.json) to YOLO format for ultralytics.

FiftyOne bbox = [x, y, w, h] normalized, top-left origin.
YOLO bbox     = [x_center, y_center, w, h] normalized.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "vision" / "CarDD"
OUT = ROOT / "data" / "vision" / "CarDD_yolo"
IMG_DIR = SRC / "data"
VAL_FRACTION = 0.15

CLASSES = ["crack", "dent", "glass shatter", "lamp broken", "scratch", "tire flat"]
CLS_IDX = {c: i for i, c in enumerate(CLASSES)}


def main() -> None:
    samples = json.load(open(SRC / "samples.json"))["samples"]
    print(f"{len(samples)} samples in CarDD")

    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT / "labels" / split).mkdir(parents=True, exist_ok=True)

    n = {"train": 0, "val": 0}
    skipped = 0
    every = int(round(1 / VAL_FRACTION))  # ~every 7th sample -> val (~15%)
    for i, s in enumerate(samples):
        name = Path(s["filepath"]).name
        img = IMG_DIR / name
        if not img.exists():
            skipped += 1
            continue
        split = "val" if i % every == 0 else "train"

        lines = []
        for det in (s.get("detections") or {}).get("detections", []):
            label = det.get("label")
            if label not in CLS_IDX:
                continue
            x, y, w, h = det["bounding_box"]
            xc, yc = x + w / 2, y + h / 2
            lines.append(f"{CLS_IDX[label]} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

        # symlink image (saves disk), write label file (may be empty = background)
        dst = OUT / "images" / split / name
        if not dst.exists():
            dst.symlink_to(img.resolve())
        (OUT / "labels" / split / f"{img.stem}.txt").write_text("\n".join(lines))
        n[split] += 1

    yaml = (
        f"path: {OUT}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"nc: {len(CLASSES)}\n"
        f"names: {CLASSES}\n"
    )
    (OUT / "cardd.yaml").write_text(yaml)
    print(f"train={n['train']}  val={n['val']}  skipped(missing img)={skipped}")
    print(f"data.yaml -> {OUT/'cardd.yaml'}")


if __name__ == "__main__":
    main()
