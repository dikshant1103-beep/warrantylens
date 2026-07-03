"""Sync media utilities for the Celery worker: ffprobe metadata, ffmpeg frame
extraction, sharpness scoring and perceptual-hash dedup. Requires ffmpeg/ffprobe
on PATH."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

MAX_FRAMES = 60          # cap stored frames per video (cost control)
SAMPLE_FPS = 1.0         # extract ~1 frame/second
DEDUP_HAMMING = 5        # near-duplicate threshold (aHash distance)
MIN_SHARPNESS = 5.0      # drop very blurry frames


@dataclass
class ProbeResult:
    duration_s: float | None
    width: int | None
    height: int | None


@dataclass
class ExtractedFrame:
    local_path: str
    timestamp_s: float
    frame_index: int
    sharpness: float


def probe(path: str) -> ProbeResult:
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout or "{}")
    duration = None
    fmt = data.get("format", {})
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except ValueError:
            duration = None
    width = height = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            width = s.get("width")
            height = s.get("height")
            break
    return ProbeResult(duration_s=duration, width=width, height=height)


def _sharpness(img: Image.Image) -> float:
    """Variance of the discrete Laplacian (focus measure)."""
    g = np.asarray(img.convert("L"), dtype=np.float64)
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    lap = (
        4 * g[1:-1, 1:-1]
        - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    )
    return float(lap.var())


def _ahash(img: Image.Image) -> int:
    small = np.asarray(img.convert("L").resize((8, 8)), dtype=np.float64)
    bits = (small > small.mean()).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def extract_frames(video_path: str, out_dir: str) -> list[ExtractedFrame]:
    """Sample frames at SAMPLE_FPS, dedup near-duplicates, drop blurry ones,
    keep the sharpest up to MAX_FRAMES."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    pattern = str(Path(out_dir) / "raw_%05d.jpg")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video_path,
        "-vf", f"fps={SAMPLE_FPS}", "-q:v", "3", pattern,
    ]
    subprocess.run(cmd, check=True)

    raw = sorted(Path(out_dir).glob("raw_*.jpg"))
    kept: list[ExtractedFrame] = []
    hashes: list[int] = []

    for i, p in enumerate(raw):
        try:
            img = Image.open(p)
            img.load()
        except Exception:
            continue
        h = _ahash(img)
        if any(_hamming(h, prev) <= DEDUP_HAMMING for prev in hashes):
            p.unlink(missing_ok=True)
            continue
        sharp = _sharpness(img)
        if sharp < MIN_SHARPNESS:
            p.unlink(missing_ok=True)
            continue
        hashes.append(h)
        kept.append(
            ExtractedFrame(
                local_path=str(p),
                timestamp_s=i / SAMPLE_FPS,
                frame_index=i,
                sharpness=sharp,
            )
        )

    # Keep the sharpest MAX_FRAMES, preserving chronological order.
    if len(kept) > MAX_FRAMES:
        keep_set = {
            f.local_path
            for f in sorted(kept, key=lambda f: f.sharpness, reverse=True)[:MAX_FRAMES]
        }
        for f in kept:
            if f.local_path not in keep_set:
                Path(f.local_path).unlink(missing_ok=True)
        kept = [f for f in kept if f.local_path in keep_set]

    return kept
