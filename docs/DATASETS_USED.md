# Datasets & Models Actually Used

This documents what was **actually downloaded, trained, and shipped** in WarrantyLens — as opposed to
[`DATASETS_ONLINE.md`](./DATASETS_ONLINE.md), which is the original sourcing *plan*.

> No datasets or model weights are committed to this repo (see `.gitignore`) — only the scripts that
> download/convert/train them. Paths below refer to the local layout they create.

---

## 1. CarDD — car damage images (the main vision dataset)

| | |
|---|---|
| What | **CarDD (Car Damage Detection)** — ~4,000 real photos of damaged cars with bounding boxes |
| Classes | `dent`, `scratch`, `crack`, `glass shatter`, `lamp broken`, `tire flat` |
| Source | Hugging Face mirror [`harpreetsahota/CarDD`](https://huggingface.co/datasets/harpreetsahota/CarDD) (FiftyOne format, no auth needed) |
| License | Research/educational use — see the original [CarDD paper](https://cardd-ustc.github.io/) (Wang et al., IEEE T-ITS 2023) |
| Local path | `data/vision/CarDD` → converted to `data/vision/CarDD_yolo` |
| Scripts | `scripts/prepare_cardd_yolo.py` (FiftyOne → YOLO format, 2,412 train / 403 val split) |

**Used to fine-tune the production detector** `models/ev_defects.pt`:

- Base: YOLOv11-nano, 40 epochs, 512 px, batch 8 (fits a 4 GB GTX 1650 Ti)
- Script: `scripts/train_yolo_cardd.py`
- Results: **mAP50 = 0.680**, mAP50-95 = 0.551, precision 0.654, recall 0.666
- This is the model mounted into the Celery worker (`YOLO_WEIGHTS=/app/models/ev_defects.pt`)

## 2. Roboflow rust/corrosion sets (experiment — parked)

| | |
|---|---|
| What | [`corrosion-detection-cfgya`](https://universe.roboflow.com) (543 imgs) + [`rust-detection-k9eci`](https://universe.roboflow.com) (367 imgs) from Roboflow Universe |
| Local path | `data/vision/rf/`, merged into `data/vision/merged_yolo` |
| Scripts | `scripts/merge_datasets.py` + `scripts/train_yolo_merged.py` → `models/ev_defects_v2.pt` |

**Honest result: rust/corrosion detection failed.** The merged v2 model kept the CarDD classes strong
(glass shatter 0.985, tire flat 0.977, lamp broken 0.858 mAP50) but rust = 0.143 and corrosion = 0.032 —
the source imagery is industrial/copper corrosion, a domain mismatch with vehicle panels, and the sets are
small and inconsistently labeled. v2 is **not deployed**; v1 (`ev_defects.pt`) remains the live detector.
Rust detection is documented as future work (needs 640 px, more epochs, better vehicle-specific data).

## 3. carclaims — real insurance-fraud tabular data

| | |
|---|---|
| What | **carclaims** (Angoss/Oracle vehicle-insurance fraud benchmark) — 15,420 real claims, 923 labeled fraud (~6%), 33 features (make, policy type, vehicle price, accident/claim history…). Used in 17+ published papers. |
| Source | GitHub mirror: `raw.githubusercontent.com/Rashmi-77/Vehicle-Insurance-Fraud-Detection/main/carclaims.csv` |
| Local path | `data/fraud/carclaims.csv` |
| Script | `scripts/train_fraud.py` → `models/fraud_xgb.joblib` + `models/fraud_metrics.json` |

Trained an XGBoost classifier (class-weighted, **no synthetic oversampling**):
**ROC-AUC 0.854** (consistent with published results on this dataset), PR-AUC 0.269,
best-F1 threshold → recall 37% / precision 28%. SHAP top features: fault attribution,
liability-only policy, age, vehicle year.

**Important caveat:** this is *insurance*-domain data — the closest public proxy that exists.
There is **no public EV-warranty-fraud dataset** (we verified; it's all proprietary). So this model is a
standalone real-data demonstrator; the in-app risk engine (`risk_service.py`) stays a transparent,
evidence-linked heuristic, and every output is advisory — the system never claims fraud.

## 4. Synthetic & simulated data (by design)

- **VIN plates for OCR** — synthetically generated VIN images with ISO-3779 checksum-valid VINs
  (validator + tests in `backend/app/ml/postprocess/vin.py`). Real per-vehicle VIN photo datasets don't exist publicly.
- **Vehicle telemetry** — generated in-app by `backend/app/ml/telemetry_sim.py` (numpy, deterministic per-VIN seed).
  Four ground-truth profiles — `normal`, `abuse`, `latent_defect`, `water_impact` — inject realistic signatures
  (harsh events + overcurrent for abuse; a slow component-temperature ramp for a latent defect). No public
  per-VIN EV telemetry exists, so simulation with known ground truth is the honest option — and it lets the
  defect-vs-abuse verdict be validated against profiles we control.
- **Battery Health Reports** — JSON schema (`backend/app/schemas/battery.py`) designed to be fed by a separate
  battery-analytics system; sample reports in `demo_images/sample_battery_report_{abuse,defect}.json`.
- **Demo inspection uploads** — CarDD-derived damage photos (kept out of the repo for licensing; see
  `demo_images/README.md`).

## 5. Pretrained models used as-is (no training data needed)

| Model | Role | Runtime |
|---|---|---|
| **Qwen2.5-VL 7B** (`qwen2.5vl:7b`) | Vision-language damage description on keyframes | Ollama, local |
| **YOLOv11n** | Base for fine-tuning (above) | Ultralytics |
| **Tesseract** | OCR for VIN / serial plates (`--psm 6`) | pytesseract in worker |
| **faster-whisper large-v3** | Mechanic voice-note transcription (English + Hinglish) | worker |
| **BGE-M3** | Multilingual embeddings for evidence search | + Qdrant vector DB |

All AI stages are feature-flagged (`AI_ENABLED`, `VLM_ENABLED`, …) and skip gracefully when a model
isn't installed — the platform runs without any of them.

## 6. Reproducing the models

```bash
# 1. CarDD → YOLO detector
python scripts/prepare_cardd_yolo.py          # downloads CarDD via HF/FiftyOne, converts to YOLO
python scripts/train_yolo_cardd.py            # → models/ev_defects.pt

# 2. (optional, parked) merged rust/corrosion experiment
python scripts/merge_datasets.py && python scripts/train_yolo_merged.py

# 3. fraud classifier on carclaims
python scripts/train_fraud.py                 # expects data/fraud/carclaims.csv → models/fraud_xgb.joblib
```
