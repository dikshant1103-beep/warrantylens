# Demo Images

Sample evidence for demoing WarrantyLens. In the app: **Claims → + New claim**,
create the draft, then upload one or more of these and **Upload & submit**.

- `damage_1.jpg` … `damage_10.jpg` — real vehicle-damage photos (from the CarDD
  dataset) → exercise **YOLO damage detection** + **Qwen2.5-VL** descriptions →
  produce a non-zero **risk score**.
- `vin_plate_1.jpg`, `vin_plate_2.jpg` — VIN plates with valid VINs → exercise
  **Tesseract OCR** VIN extraction.

Tip for a strong demo: create one claim with a couple of `damage_*` images (shows
detection + risk) and another with a `vin_plate_*` image (shows OCR VIN reading).
