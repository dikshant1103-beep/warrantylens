# WarrantyLens — AI EV Warranty Inspection Assistant

AI assistant that helps warranty reviewers verify EV inspection evidence faster and surface
suspicious claims. **Advisory only — humans make every final decision. The system never claims fraud.**

> Architecture, data plan, and dataset sources live in [`docs/`](./docs).
> This repo currently implements **Sprint 1: foundation + authentication**.

## Stack
- **Backend:** FastAPI · SQLAlchemy 2.0 (async) · Alembic · PostgreSQL · Redis · Celery · Docker
- **Frontend:** Next.js · TypeScript · TailwindCSS · ShadCN · React Query
- **AI (later sprints):** Qwen2.5-VL · YOLOv11 · PaddleOCR · Whisper · BGE-M3 · Qdrant
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
backend/    FastAPI app, models, services, auth, migrations, tests
frontend/   Next.js app (shell, login, dashboard)
docs/       ARCHITECTURE.md, DATA_PLAN.md, DATASETS_ONLINE.md
```

## Sprint status
- [x] **Sprint 1** — foundation + auth (multi-tenant, JWT, RBAC, audit log)
- [x] **Sprint 2** — claims & evidence (catalog, claim CRUD, presigned S3 uploads, Celery frame extraction)
- [x] **Sprint 3** — AI pipeline (Whisper ASR, YOLOv11, PaddleOCR+VIN, Qwen2.5-VL via Ollama, BGE-M3+Qdrant)
- [x] **Sprint 4** — scoring (completeness + explainable risk), PDF report, reviewer workflow, dashboard
- [x] **Sprint 5** — hardening (security headers, rate limiting, Prometheus, prod guards, gunicorn) — see [docs/PRODUCTION_READINESS.md](./docs/PRODUCTION_READINESS.md)
