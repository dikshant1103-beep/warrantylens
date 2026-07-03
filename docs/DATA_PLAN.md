# WarrantyLens — Data Plan

> Context: **mixed EV fleet (2-wheeler + 4-wheeler)**, **starting fresh (no historical media/outcomes)**, narration in **English + Hindi/Hinglish**.
> Core decision: **launch on zero-training models; build YOLO from our own data via a flywheel.** Date: 2026-06-16.

---

## 1. Which models need data (final)

| Model | Needs training data? | Day-1 status |
|---|---|---|
| Whisper (ASR) | No | ✅ works (multilingual, Hinglish) — add part-name glossary |
| PaddleOCR (VIN/serial) | No (optional fine-tune later) | ✅ works — supply VIN/serial format rules |
| Qwen2.5-VL (description, risk, completeness reasoning) | No (few-shot prompts) | ✅ works |
| BGE-M3 (embeddings) | No | ✅ works |
| **YOLOv11 (component + defect detection)** | **Yes — our own data** | ⛔ deferred; built from collected data |

**Implication:** the MVP ships with full functionality using VLM+OCR+Whisper. YOLO is a *cost/throughput optimization* added later, not a launch blocker.

---

## 2. Phased data strategy (because we start fresh)

```
Phase A  (Weeks 1–8, MVP build)
   Build product on VLM + OCR + Whisper. NO YOLO needed.
   IN PARALLEL: deploy standardized capture protocol at the service centre,
   start collecting inspections from day one.
        ↓
Phase B  (Weeks 4–10, overlapping)
   Label collected data (VLM pre-labels → human corrects).
   Train YOLO COMPONENT localizer first (easy, high value).
        ↓
Phase C  (ongoing flywheel)
   Reviewer confirmations → defect labels → periodic YOLO fine-tunes.
   YOLO gradually takes over cheap high-volume detection from the VLM.
```

We are never blocked: every phase ships value on its own.

---

## 3. Standardized capture protocol (this IS the dataset)

A fixed shot list per vehicle class makes every video instantly labelable and powers the completeness score. Mechanics follow it; the app guides them.

### 3.1 Two-wheeler shot list
1. Full vehicle: front-3/4, rear-3/4, left side, right side
2. Charging port — closed, open, connector mated
3. VIN / chassis-number plate (close-up, readable)
4. Battery enclosure exterior + **seals** + **fasteners** (close-up)
5. Motor (hub/mid) close-up
6. Controller housing
7. Footboard — top + underside
8. Lights (head + tail), mirrors, mudguards (front + rear)
9. Side panels (both)
10. **Claimed-damage area: 3 angles + macro close-up + a scale reference** (coin/ruler/finger)
11. Spoken narration throughout (what, where, suspected cause)

### 3.2 Four-wheeler shot list
1. 4 corners (3/4 views), all door/body panels, bumpers
2. Charging port(s) — AC and DC if present, flap + connector
3. VIN — windshield + door-jamb sticker (both)
4. Under-hood: motor/controller housing(s)
5. **Underbody pass** for battery enclosure (impact / water-ingress), seals, fasteners (needs lift/ramp)
6. Lights, mirrors, mudguards/wheel arches
7. **Claimed-damage area: 3 angles + macro + scale reference**
8. Spoken narration throughout

### 3.3 Capture quality rules (enforced/encouraged in app)
- Good, even lighting; avoid harsh glare on labels.
- Hold each shot ~2–3 s steady (gives sharp frames).
- Macro/close-up for any defect; include a scale reference.
- Minimum total video length per template; required views must all appear.
- The completeness engine checks these → mechanic re-shoots *before* leaving the bay.

---

## 4. YOLO dataset specification

### 4.1 Classes
**Component classes (localization):** charging_port, charging_connector, wiring_harness, motor_housing, controller_housing, battery_enclosure, side_panel, body_panel, footboard, headlight, tail_light, mirror, mudguard, protective_cover, seal, fastener.

**Defect/indicator classes (detection):** crack, scratch, impact_dent, broken, missing_part, corrosion, rust, water_stain, tamper_mark, missing_seal, opened_enclosure, non_standard_mod.

(Modeled two-stage: locate component region → classify defects on the crop. Better with small data.)

### 4.2 Volume targets
| Milestone | Labeled images/instances | Outcome |
|---|---|---|
| YOLO v0 (component localizer) | ~100–200 imgs/component | usable localization |
| YOLO v1 (defects, common) | ~300–800 instances/defect class for scratch/dent/crack/rust | usable defect detection |
| YOLO v1 total | ~1,000–2,000 labeled frames | ships behind/alongside VLM |
| Hard classes (tamper, water_ingress, opened_enclosure, missing_seal) | rare → keep VLM-led longer | flywheel-grown |

### 4.3 Collection math (fresh start)
At ~20–40 inspections/week, 4 weeks ≈ 100–160 inspections ≈ **tens of thousands of frames** (pre-dedup). After dedup/sharpness filter, easily enough to label 1–2k for YOLO v1.

### 4.4 Labeling workflow
- Tool: **Roboflow** (fast start, auto-label) or **CVAT** (self-hosted, free, full control).
- **Pre-label with VLM + COCO-pretrained YOLO**, humans only correct → 5–10× faster.
- Active learning: prioritize low-confidence / VLM-vs-YOLO disagreement frames.
- ~1 trained annotator, part-time, ~2–4 weeks for the first usable set.

---

## 5. Public datasets for transfer pre-training (head start only)

None are EV-specific; they only pre-train the common damage classes so we need fewer of our own frames.

| Dataset | Helps with | Note |
|---|---|---|
| **CarDD** (~4k imgs) | scratch, dent, crack, glass-shatter, broken-lamp, flat-tire | best general car-damage starter |
| Roboflow car scratch/dent sets | scratch, dent | free, several thousand imgs |
| Corrosion/rust detection sets | corrosion, rust | metal/structural corrosion |
| Crack datasets (SDNET etc.) | crack texture | transfer texture, not object |

⚠️ No public source covers charging ports, battery enclosures, EV footboards, seals, tamper/opened-enclosure. Those are **100% our own data** — and that's the moat.

---

## 6. OCR data
- No training needed for MVP. Supply:
  - **VIN rules:** 17 chars, exclude I/O/Q, ISO-3779 checksum (position 9).
  - **Serial regexes** per component (collect real examples from the catalog).
- Later optional: ~100–200 real label photos to fine-tune PaddleOCR for glare / curved stickers / embossed plates.

---

## 7. ASR data
- Whisper `large-v3` (best Hinglish) or `medium` (cheaper); auto language detect.
- **Part-name glossary** to bias decoding (English + common Hindi terms), e.g.:
  charging port, connector, harness, motor, controller, enclosure, footboard, mudguard, mirror, seal, fastener, crack (darar), dent, scratch (khrronch), rust/corrosion (jung), leak/water (paani/leak), broken (toota), missing (gayab), tamper (cheda-chaadi).
- No training; just config + glossary. Validate accuracy on 10–20 real recordings per language.

---

## 8. Risk-model data (important expectation-setting)
- **No historical claim outcomes → no supervised risk classifier for a long time.**
- Risk engine stays **heuristic + explainable + admin-tunable** (this is the correct, defensible MVP design anyway).
- To enable a learned risk re-ranker in V2, we must accumulate **reviewer decisions** (approve/reject/needs-more) as labels — the platform generates these automatically once live. Plan: ~6–12 months of decisions before a learned re-ranker is worth attempting, and only with explainability.

---

## 9. Data governance from day one
- Consent/ownership: confirm the service centre can use captured media for model training (put in the agreement).
- PII: VIN + incidental faces/plates → retention policy now, auto-blur in V2.
- Storage: raw media immutable in S3 with sha256; training sets versioned (DVC or Roboflow versions).
- Tenant isolation: training data segregated per tenant unless contractually pooled.

---

## 10. Action checklist (what to start NOW, before/while coding)
- [ ] Confirm 2W + 4W component lists with the service centre; finalize shot lists.
- [ ] Get sign-off to use captured media for training (data clause).
- [ ] Stand up capture protocol — even a phone + checklist works week 1.
- [ ] Start collecting standardized inspections immediately (target 20–40/week).
- [ ] Collect 20–30 real VIN/serial label photos (OCR rules + later fine-tune).
- [ ] Collect 10–20 narration samples per language (Whisper validation + glossary).
- [ ] Pull CarDD + a rust set for YOLO transfer pre-training.
- [ ] Pick labeling tool (Roboflow vs CVAT) + assign an annotator.
```
