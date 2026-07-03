# WarrantyLens — Making the AI Actually Detect False Claims

> The current risk engine is a transparent **heuristic** (rules + weights). This doc
> is the plan to add a **learned, fine-tuned** false-claim detector. Two models.

## The honest framing
"Detect false warranty claims" = two separate ML problems:
1. **Vision** — extract evidence from media (damage, tamper, rust, missing seals, opened enclosure).
2. **Fraud classifier** — combine evidence + claim metadata → false-claim probability.

There is **no public EV-warranty-fraud dataset** (proprietary to OEMs/insurers).
So model #2 is trained on a public **insurance-fraud proxy** and/or a **synthetic
dataset built on our own feature schema**, and improved over time by the reviewer-
decision flywheel. We always present the output as an **advisory risk score with
explanations**, never a fraud verdict.

---

## Model A — Vision (fine-tune YOLOv11)
Goal: real detection of EV damage + tamper indicators feeding the classifier.

Datasets (also in DATASETS_ONLINE.md §9b):
- CarDD (damage): https://huggingface.co/datasets/harpreetsahota/CarDD
- Roboflow car damage: https://universe.roboflow.com/yolov8-z6snb/car-damage-7dsxw
- Roboflow car parts (components): https://universe.roboflow.com/car-segmentation-iq9jj/car-parts-9vig8
- Roboflow corrosion / rust: https://universe.roboflow.com/custom-uu1w8/corrosion-detection-cfgya
- NEU / Severstal (metal defects): https://www.kaggle.com/datasets/kaustubhdikshit/neu-surface-defect-database
- Tamper / opened-enclosure / missing-seal: scrape images → **Autodistill + GroundedSAM** auto-label (no manual annotation).

Train: `ultralytics` YOLOv11 on merged + auto-labeled set → checkpoint → set
`YOLO_WEIGHTS=/models/ev_defects.pt`, `YOLO_ENABLED=true`.

Output features per claim: `defect_count`, `defect_types`, `max_severity`,
`tamper_detected`, `missing_seal`, `opened_enclosure`, `rust_present`.

---

## Model B — False-claim classifier (XGBoost/LightGBM, SHAP-explainable)

### Option 1 — Public insurance-fraud proxy (proves the method)
- ⭐ Vehicle Insurance Claim Fraud (~15k, `FraudFound`): https://www.kaggle.com/datasets/shivamb/vehicle-claim-fraud-detection
- Auto Insurance Claims Fraud (`fraud_reported`): https://www.kaggle.com/datasets/mastmustu/insurance-claims-fraud-data
- Mirrors: https://www.kaggle.com/datasets/arpan129/insurance-fraud-detection ·
  https://www.kaggle.com/datasets/antopravinjohnbosco/auto-insurance-claims-fraud-detection

Use to: learn the workflow (class imbalance handling, SMOTE, ROC-AUC, SHAP) and
benchmark. Limitation: insurance schema ≠ warranty schema.

### Option 2 — Synthetic dataset on OUR feature schema (recommended for the project)
Generate N synthetic claims with the EXACT features our pipeline produces, plus a
programmatic fraud label (rules + noise). This yields a classifier that plugs
directly into the pipeline.

Feature vector (what the pipeline already computes):
```
vin_mismatch (0/1), completeness_score (0-100), defect_count, max_severity,
tamper_detected (0/1), opened_enclosure (0/1), missing_seal (0/1),
rust_present (0/1), water_ingress (0/1), narrative_image_mismatch (0/1),
claim_age_days, component_category, num_media, num_keyframes
```
Label rule (example, with noise so it's learnable not trivial):
`fraud_prob ↑ with tamper/opened_enclosure/vin_mismatch/water_ingress + low completeness`.

Train: XGBoost/LightGBM → calibrated probability → SHAP values per claim →
map to the existing `risk_assessments.factors` (so the UI/report stay identical).
Swap `risk_service` heuristic for the model behind the same interface.

### Option 3 — Real flywheel (production)
Accumulate reviewer decisions (`reviews.decision`) as labels over months → retrain
on real outcomes. This is the only path to a genuinely real warranty-fraud model;
it requires live usage first.

---

## Recommended build order
1. **YOLOv11 fine-tune** (Model A) on CarDD + Roboflow + auto-labeled EV images.
2. **Synthetic claim generator** + **XGBoost classifier** (Model B, Option 2) on our
   feature schema, with SHAP → drop into `risk_service` behind the existing interface.
3. Validate on the **insurance-fraud proxy** (Option 1) to report real ROC-AUC in the writeup.
4. Wire the flywheel (Option 3) for the future-work section.

## Deps
`pip install -e ".[ai]"` (already done) + `xgboost lightgbm scikit-learn shap imbalanced-learn`.

## Honesty statement (put in the project writeup)
- Vision model: fine-tuned on public car-damage data; EV-specific classes are weak
  until more EV images are labeled (flywheel).
- Fraud classifier: trained on synthetic + insurance-proxy data — demonstrates the
  method; real warranty-fraud accuracy requires proprietary labeled claims.
- Output is always advisory risk + explanation; the human reviewer decides.
