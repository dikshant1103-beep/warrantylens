# WarrantyLens — Online-Only Dataset Sourcing (Project Mode)

> Constraint: **this is a project — no manual data collection, no service-centre access.**
> Goal: assemble everything from public sources + auto-labeling + synthetic generation.
> Date: 2026-06-16.

---

## 0. Principle
A project must **demonstrate the architecture end-to-end on representative data** — not build a production-grade EV detector. Public + auto-labeled + synthetic data is sufficient and standard. Known gaps (EV-specific parts) are documented as limitations + future work.

---

## 1. What each model needs (project mode)

| Model | Data plan |
|---|---|
| Whisper (ASR) | Pretrained. Audio = from downloaded videos / TTS / one self-recorded sample. |
| PaddleOCR | Pretrained. VIN images scraped + synthetic VIN labels. |
| Qwen2.5-VL | Pretrained, zero/few-shot. No data. |
| BGE-M3 | Pretrained. No data. |
| YOLOv11 | **Optional.** Train on Roboflow/CarDD + auto-labeled scraped images. OR skip and use Grounding DINO + VLM at inference. |

---

## 2. Inspection videos (the "mechanic uploads")

Use **`yt-dlp`** to download real walkaround / inspection / damage / repair videos. These ARE inspection videos.

Search queries that work well:
- `EV scooter PDI` / `electric scooter walkaround`
- `Ola S1 / Ather / TVS iQube / Chetak damage` / `delivery damage`
- `EV car delivery inspection` / `Tesla PDI inspection`
- `electric scooter repair` / `EV charging port` / `EV motor`
- `car damage inspection` / `vehicle scratch dent walkaround`

```
yt-dlp -f "mp4[height<=720]" "<url or ytsearch10:EV scooter PDI inspection>"
```
Keep 10–30 clips, trim to 1–3 min → your test corpus of "uploads." Many already have spoken narration → free ASR test data.

⚠️ Use for a non-commercial project/demo only; respect platform terms and don't redistribute.

---

## 3. Damage detection datasets (pre-labeled, downloadable)

### Roboflow Universe (best source — many YOLO-ready)
Search and export in **YOLOv11/YOLOv8 format**:
- `car damage detection`, `vehicle damage`, `car scratch and dent`
- `car parts` / `vehicle parts` (component classes)
- `corrosion` / `rust detection`
- `license plate` (for OCR region practice)
- possibly `charging port`, `ev` (hit-or-miss)

### Kaggle
- **CarDD** (Car Damage Detection) — ~4k imgs: scratch, dent, crack, glass-shatter, broken-lamp, flat-tire.
- "Car Damage Detection" / "Coco Car Damage Detection Dataset".
- **Severstal Steel Defect Detection** — metal surface cracks/scratches/pitting (great for corrosion/crack transfer).
- **NEU Surface Defect Database** — 6 metal-surface defect classes.

### Academic
- **CarDD** official release (paper + data).
- **SDNET2018** — crack images (texture transfer).

These cover: scratch, dent, crack, broken, rust/corrosion, flat-tire, glass-shatter. Train YOLOv11 directly — already labeled.

---

## 4. EV-specific components → scrape + AUTO-LABEL (no manual annotation)

No ready dataset for charging_port, footboard, motor_housing, battery_enclosure, seals, fasteners. So:

### Step 1 — gather images
- Scrape Bing/Google Images per component (`bing-image-downloader` / `icrawler`).
- Or grab frames from the YouTube videos (you already have them).

### Step 2 — auto-label with open-vocabulary models (ZERO hand-labeling)
- **Autodistill** + **GroundedSAM** / **Grounding DINO**: give text prompts → get YOLO labels.
  ```
  ontology = {
    "charging port": "charging_port",
    "motor housing": "motor_housing",
    "headlight": "headlight",
    "side panel": "side_panel",
    "cracked surface": "crack",
    "rusty metal": "rust",
    ...
  }
  ```
  Run over the image folder → exports a labeled YOLO dataset automatically.
- Spot-check a sample for sanity; fix obvious misses (optional, minutes not days).

### Step 3 — train YOLOv11 on the auto-labeled set.

This is the key move: **"find data online" + "auto-label it" = a full custom dataset with no manual work.**

---

## 5. VIN / serial OCR data

- PaddleOCR is pretrained → works on real plate/label photos as-is.
- For VIN samples: scrape `VIN plate` / `chassis number plate` images, or **generate synthetic VINs**:
  - Render valid 17-char VINs (ISO-3779 checksum) with PIL onto metal/sticker textures, add blur/glare/rotation augmentation → unlimited labeled OCR pairs.
- This also gives clean ground truth to *evaluate* OCR accuracy.

---

## 6. Speech / narration (Hinglish + English)

Options (pick any):
- **Reuse audio** from the downloaded walkaround videos (many narrate in Hindi/English).
- **TTS-generate** scripted narrations (e.g., Coqui/Edge-TTS) in English + Hindi → labeled transcripts for evaluation.
- **Record one or two yourself** for realism.

Whisper needs no training — this is just test/eval material + glossary tuning.

---

## 7. Two build tiers (choose based on effort)

| | Tier 1 — Inference-only | Tier 2 — Trained YOLO (recommended for portfolio) |
|---|---|---|
| Detection | Grounding DINO + Qwen2.5-VL, no training | Train YOLOv11 on §3 + §4 auto-labeled data |
| Effort | Lowest — runs day one | +~1 day (auto-label + train) |
| Demo quality | Good | Better; shows ML engineering |
| Story | "open-vocab VLM detection" | "custom detector + flywheel" |

Recommendation: **start Tier 1** (unblocks the whole pipeline immediately), then **add Tier 2** YOLO as a polish step.

---

## 8. Tooling summary
- `yt-dlp` — inspection videos
- `bing-image-downloader` / `icrawler` — component images
- **Autodistill + GroundedSAM / Grounding DINO** — auto-labeling
- **Roboflow** — dataset hosting/export, also has auto-label
- `ultralytics` (YOLOv11) — training
- PIL/`Pillow` + Edge-TTS/Coqui — synthetic VIN + narration

---

## 9. Honest limitations to document in the project
- Damage data is car-centric; EV-specific defects (tamper, opened enclosure, seal damage) are weakly represented → detector strongest on scratch/dent/crack/rust.
- Auto-labels are noisier than human labels → acceptable for a demo; flagged as future work.
- No real warranty outcomes → risk engine is heuristic/explainable (by design), not learned.
- These are **future-work / flywheel** items, not project blockers.

---

## 9b. DIRECT DOWNLOAD LINKS (verified 2026-06-16)

### Damage on cars (primary YOLO training data)
- **CarDD** (4k imgs, 6 classes: dent/scratch/crack/glass-shatter/lamp-broken/tire-flat)
  - Official (license form, academic): https://cardd-ustc.github.io/
  - **HuggingFace mirror (direct, no form):** https://huggingface.co/datasets/harpreetsahota/CarDD
- **Kaggle — Coco Car Damage Detection** (COCO json): https://www.kaggle.com/datasets/lplenka/coco-car-damage-detection-dataset
- **Roboflow — car damage** (YOLO export): https://universe.roboflow.com/yolov8-z6snb/car-damage-7dsxw
- **Roboflow — Cars-Part-Damage-Detection** (damage tied to parts): https://universe.roboflow.com/car-damage-detection-final/cars-part-damage-detection/dataset/3

### Vehicle components (for component localization head)
- **Ultralytics Carparts-seg** — 23 classes, **one-line auto-download, no account** (BEST starting point): https://docs.ultralytics.com/datasets/segment/carparts-seg
- **Roboflow — Car Parts** (21 classes incl. headlight/bumper): https://universe.roboflow.com/car-segmentation-iq9jj/car-parts-9vig8
- **Roboflow — Car Parts YOLO V11** (47 detailed classes): https://universe.roboflow.com/pfe-9kkt6/car-parts-yolo-v11-nqnhg

### Rust / corrosion
- **Roboflow — corrosion detection** (639 imgs): https://universe.roboflow.com/custom-uu1w8/corrosion-detection-cfgya
- **Roboflow — rust detection** (153 imgs): https://universe.roboflow.com/object-detection-i3hzf/rust-detection-k9eci

### Metal-surface defects (transfer for crack/scratch/pitting texture)
- **NEU Surface Defect DB** (1,800 imgs, 6 classes): https://www.kaggle.com/datasets/kaustubhdikshit/neu-surface-defect-database
- **Severstal Steel Defect** (18k imgs, pixel masks): https://www.kaggle.com/c/severstal-steel-defect-detection

### How to download each
- **Kaggle:** install token (`~/.kaggle/kaggle.json`), then
  `kaggle datasets download -d lplenka/coco-car-damage-detection-dataset`
  `kaggle datasets download -d kaustubhdikshit/neu-surface-defect-database`
  `kaggle competitions download -c severstal-steel-defect-detection`
- **Roboflow:** `pip install roboflow`, get free API key, or click **Download Dataset → YOLOv11** on the page.
- **HuggingFace (CarDD):** `huggingface-cli download harpreetsahota/CarDD --repo-type dataset --local-dir ./CarDD`
- **Ultralytics carparts:** nothing to download manually — referencing `carparts-seg.yaml` in training auto-fetches it.

> Licensing note: these are public/research datasets. Fine for a non-commercial project; check each dataset's license before any commercial use.

## 10. Quick-start order
1. `yt-dlp` ~15 inspection videos → test uploads.
2. Download CarDD + 1–2 Roboflow damage sets (YOLO format).
3. Scrape component images → Autodistill auto-label → merge.
4. Train YOLOv11 (Tier 2) — or skip for Tier 1.
5. Synthetic VIN set for OCR eval.
6. TTS/reused audio for ASR eval.
→ Full representative dataset, **zero manual labeling.**
```
