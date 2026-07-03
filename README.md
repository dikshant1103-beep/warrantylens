# WarrantyLens — AI EV Warranty Inspection Assistant

AI assistant that helps warranty reviewers verify EV inspection evidence faster and surface
suspicious claims. **Advisory only — humans make every final decision. The system never claims fraud.**

> Architecture, data plan, and dataset sources live in [`docs/`](./docs).
> **What data trained what:** see [docs/DATASETS_USED.md](./docs/DATASETS_USED.md).

## Stack
- **Backend:** FastAPI · SQLAlchemy 2.0 (async) · Alembic · PostgreSQL · Redis · Celery · Docker
- **Frontend:** Next.js · TypeScript · TailwindCSS · ShadCN · React Query
- **AI:** Qwen2.5-VL (Ollama) · YOLOv11 fine-tuned on CarDD · Tesseract OCR · faster-whisper · BGE-M3 · Qdrant
- **Storage:** S3-compatible (MinIO in dev)

## Quick start (Docker)
```bash
cp .env.example .env
cp backend/.env.example backend/.env
docker compose up -d --build      # starts postgres, redis, minio, qdrant, api, frontend
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed   # demo tenant + admin user
```
- API:        http://localhost:8000  (docs at `/docs`)
- Frontend:   http://localhost:3000
- MinIO:      http://localhost:9001
- Qdrant:     http://localhost:6333/dashboard

Default seeded admin: `admin@demo.warrantylens.io` / `Admin12345!` (tenant `demo`).

## Enabling the AI pipeline (Sprint 3)
AI is **off by default** so the app runs without heavy models. To enable:
```bash
# Heavy model deps (on the worker/GPU image)
cd backend && pip install -e ".[ai]"
# VLM via Ollama (benchmarked on GTX 1650 Ti, CPU ~67s/img):
ollama serve & ollama pull qwen2.5vl:7b
```
Then set in `backend/.env`: `AI_ENABLED=true` and toggle per model
(`VLM_ENABLED`, `ASR_ENABLED`, `YOLO_ENABLED`, `OCR_ENABLED`, `EMBEDDINGS_ENABLED`).
Each stage is independent: a disabled/unavailable model is **skipped**, not failed.

## Local backend (without Docker)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# point DATABASE_URL at a running postgres, then:
alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload
```

## Project layout
```
backend/    FastAPI app, models, services, ML clients, migrations, tests
frontend/   Next.js app (dashboard, claims, vehicles/digital passport, review)
desktop/    Electron wrapper (native window over the local stack, AppImage build)
scripts/    dataset download/convert + YOLO & fraud-classifier training
docs/       ARCHITECTURE.md, DATASETS_USED.md, DATA_PLAN.md, DATASETS_ONLINE.md, FRAUD_AI_PLAN.md
```

## Datasets & models used

Full details with metrics, sources, licenses, and repro commands: **[docs/DATASETS_USED.md](./docs/DATASETS_USED.md)**. In short:

| Data | Used for | Result |
|---|---|---|
| **CarDD** (~4k real car-damage photos, HF `harpreetsahota/CarDD`) | fine-tune YOLOv11n → `ev_defects.pt`, the live detector | mAP50 0.680 |
| **Roboflow rust/corrosion** (543 + 367 imgs) | v2 detector experiment | parked — domain mismatch (rust mAP50 0.14) |
| **carclaims** (15,420 real insurance-fraud claims) | XGBoost fraud demonstrator + SHAP | ROC-AUC 0.854 |
| **Synthetic VINs** (ISO-3779 checksum-valid) | OCR / VIN extraction tests | — |
| **Simulated telemetry** (in-app, 4 ground-truth profiles) | defect-vs-abuse verdict validation | — |
| Pretrained: Qwen2.5-VL 7B, faster-whisper, Tesseract, BGE-M3 | VLM / ASR / OCR / embeddings — zero-shot | — |

No datasets or weights are committed; `scripts/` reproduces everything. There is no public EV-warranty-fraud
dataset (all proprietary), so tabular fraud modeling uses the closest real proxy (insurance) and is clearly
framed as a demonstrator — the in-app risk engine stays an explainable, evidence-linked heuristic.

## Sprint status
- [x] **Sprint 1** — foundation + auth (multi-tenant, JWT, RBAC, audit log)
- [x] **Sprint 2** — claims & evidence (catalog, claim CRUD, presigned S3 uploads, Celery frame extraction)
- [x] **Sprint 3** — AI pipeline (Whisper ASR, YOLOv11, Tesseract OCR + VIN validation, Qwen2.5-VL via Ollama, BGE-M3+Qdrant)
- [x] **Sprint 4** — scoring (completeness + explainable risk), PDF report, reviewer workflow, dashboard
- [x] **Sprint 5** — hardening (security headers, rate limiting, Prometheus, prod guards, gunicorn) — see [docs/PRODUCTION_READINESS.md](./docs/PRODUCTION_READINESS.md)
- [x] **Post-sprint** — serial-number lifecycle tracking (anti swap-and-sell), battery health reports, simulated vehicle telemetry, unified defect-vs-abuse verdict, per-VIN digital passport, Electron desktop app (AppImage)
