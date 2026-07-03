"""Merge CarDD + Roboflow rust/corrosion into one unified YOLO dataset.

Unified taxonomy (8 classes):
  0 crack  1 dent  2 glass shatter  3 lamp broken  4 scratch  5 tire flat
  6 rust   7 corrosion

CarDD already uses indices 0-5. The Roboflow sets are remapped per their own
data.yaml class names. Output: data/vision/merged_yolo/ (images symlinked, labels
rewritten with remapped class ids), plus merged.yaml.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VIS = ROOT / "data" / "vision"
OUT = VIS / "merged_yolo"

UNIFIED = ["crack", "dent", "glass shatter", "lamp broken", "scratch", "tire flat",
           "rust", "corrosion"]
IDX = {n: i for i, n in enumerate(UNIFIED)}

# How each source's class NAMES map into the unified taxonomy.
NAME_MAP = {
    "crack": "crack", "dent": "dent", "glass shatter": "glass shatter",
    "lamp broken": "lamp broken", "scratch": "scratch", "tire flat": "tire flat",
    "rust": "rust", "iron rust": "rust",
    "corrosion": "corrosion", "copper corrosion": "corrosion",
}

# Sources: (path, splits-mapping to train/val). CarDD is already split.
SOURCES = [
    {"name": "CarDD", "dir": VIS / "CarDD_yolo",
     "splits": {"train": "train", "val": "val"}, "yaml_names": UNIFIED[:6]},
    {"name": "corrosion", "dir": VIS / "rf" / "corrosion-detection-cfgya",
     "splits": {"train": "train", "valid": "val", "test": "train"}, "yaml_names": None},
    {"name": "rust", "dir": VIS / "rf" / "rust-detection-k9eci",
     "splits": {"train": "train", "valid": "val", "test": "train"}, "yaml_names": None},
]


def load_names(src) -> list[str]:
    if src["yaml_names"]:
        return src["yaml_names"]
    y = yaml.safe_load((src["dir"] / "data.yaml").read_text())
    names = y["names"]
    return list(names.values()) if isinstance(names, dict) else list(names)


def remap_label(text: str, names: list[str]) -> list[str]:
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        old = int(parts[0])
        if old >= len(names):
            continue
        uname = NAME_MAP.get(names[old].strip().lower())
        if uname is None:
            continue  # drop classes we don't model (e.g. Grado3)
        out.append(" ".join([str(IDX[uname]), *parts[1:]]))
    return out


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT / "labels" / split).mkdir(parents=True, exist_ok=True)

    counts = {"train": 0, "val": 0}
    per_source = {}
    for src in SOURCES:
        names = load_names(src)
        sc = 0
        for sub, dest_split in src["splits"].items():
            img_dir = src["dir"] / "images" / sub
            lbl_dir = src["dir"] / "labels" / sub
            if not img_dir.exists():
                # Roboflow layout: <split>/images
                img_dir = src["dir"] / sub / "images"
                lbl_dir = src["dir"] / sub / "labels"
            if not img_dir.exists():
                continue
            for img in img_dir.iterdir():
                if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    continue
                stem = img.stem
                lbl = lbl_dir / f"{stem}.txt"
                tag = f"{src['name']}_{stem}"
                dst_img = OUT / "images" / dest_split / f"{tag}{img.suffix}"
                if not dst_img.exists():
                    dst_img.symlink_to(img.resolve())
                lines = remap_label(lbl.read_text(), names) if lbl.exists() else []
                (OUT / "labels" / dest_split / f"{tag}.txt").write_text("\n".join(lines))
                counts[dest_split] += 1
                sc += 1
        per_source[src["name"]] = sc

    (OUT / "merged.yaml").write_text(
        f"path: {OUT}\ntrain: images/train\nval: images/val\n"
        f"nc: {len(UNIFIED)}\nnames: {UNIFIED}\n"
    )
    print("per-source images:", per_source)
    print("merged:", counts, "-> classes:", UNIFIED)
    print("yaml:", OUT / "merged.yaml")


if __name__ == "__main__":
    main()
