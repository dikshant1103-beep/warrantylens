# EV Warranty Inspection Platform — Architecture & Roadmap

> **Product codename:** `WarrantyLens`
> **Positioning:** AI Warranty Inspection Assistant for EV manufacturers and service centers.
> **Document status:** v1.0 — Architecture for approval. No application code yet.
> **Owner:** Founding eng (CTO-mode). **Date:** 2026-06-16.

---

## 0. Guiding Principles (read first)

1. **Human-in-the-loop, always.** The system never approves, rejects, or declares fraud. It produces *evidence*, *completeness*, and *risk indicators*. Every model output is advisory and explainable. Decision authority stays with the warranty reviewer. This is a legal, ethical, and product constraint — it shapes the data model (we store `risk_indicators`, never `is_fraud`), the UI (recommendations, not verdicts), and the audit trail.
2. **Evidence-first, model-second.** A correct, auditable, immutable evidence pipeline is more valuable than a marginally better model. We optimize for traceability: every claim links to raw media → extracted frames → detections → human review, with hashes.
3. **Async by default.** Video/AI work is long-running. The API never blocks on inference. Everything heavy goes through a Celery task graph; the client polls or subscribes.
4. **Stateless services, stateful stores.** API and workers are horizontally scalable and hold no local state. State lives in Postgres (system of record), S3 (media), Qdrant (vectors), Redis (broker/cache).
5. **Cost-aware GPU.** GPU is the dominant marginal cost. Batch, cache, downscale, and route to the cheapest model that meets the SLA. Don't run Qwen2.5-VL on frames YOLO already cleared as clean.
6. **Build to sell to OEMs.** Multi-tenant from day one (tenant_id on every row), RBAC, audit logs, data residency awareness, SOC2-friendly logging.

---

## 1. Product Requirements Document (PRD)

### 1.1 Problem
EV manufacturers lose money on warranty claims because of incomplete inspections, poor/insufficient evidence, misclassified component damage, incorrect submissions, and slow manual review. Reviewers are the bottleneck and lack tooling to verify evidence quickly.

### 1.2 Goal
Help warranty reviewers **verify evidence faster** and **surface suspicious claims** — not auto-decide. Reduce review time per claim, increase evidence completeness at submission, and create a defensible audit trail.

### 1.3 Users & Jobs-to-be-done
| Persona | Primary JTBD | Key surfaces |
|---|---|---|
| **Mechanic / Inspector** (service center) | Capture a complete, compliant inspection (video + images + spoken notes) and submit a claim with minimal rework | Guided capture, upload, completeness feedback |
| **Warranty Reviewer** (OEM / regional) | Triage a queue, verify evidence against the claim, accept/escalate with confidence and a record | Claim detail, evidence viewer, risk panel, decision + notes |
| **Admin / Tenant owner** | Manage users, components, inspection templates, thresholds, integrations | Admin console |
| **(V2) OEM analyst** | Trend fraud indicators, completeness, defect hot-spots across fleet | Analytics |

### 1.4 Functional requirements (MVP)
- FR1: Email/password auth, JWT sessions, role-based access (Admin, Reviewer, Mechanic). Multi-tenant.
- FR2: Create claim with VIN, component(s), claim reason, mechanic narrative.
- FR3: Upload inspection video(s) + images; resumable/multipart for large video.
- FR4: Async pipeline: frame extraction, ASR transcript, OCR (VIN + serials), damage detection, completeness check, risk scoring, report generation.
- FR5: Inspection report with damage summary, missing-evidence list, completeness score, risk score with rationale.
- FR6: Reviewer workflow: queue → claim detail → evidence viewer → decision (approve / request-more / escalate) + notes.
- FR7: PDF export of report.
- FR8: Dashboard: claims overview, pending reviews, risk distribution, completeness stats.
- FR9: Full audit log of every state transition and human action.

### 1.5 Non-functional requirements
- **Latency:** API p95 < 300 ms (non-AI). AI pipeline SLA: standard claim (≤2 min video, ≤20 images) processed in ≤ 8 min p95.
- **Availability:** 99.5% MVP target.
- **Durability:** Media 11 nines (S3); DB PITR backups.
- **Security:** Encryption in transit + at rest; tenant isolation; signed URLs; audit immutability.
- **Scalability:** 10k claims/day at V2 without architectural change.
- **Explainability:** every risk score decomposes into named, evidence-linked factors.
- **Privacy/compliance:** PII = VIN + faces/plates incidentally captured. Face/plate blurring (V2), data retention policy, region pinning.

### 1.6 Explicitly out of scope
Battery RUL, battery health/SoH, battery telemetry, CAN-bus, vehicle performance analytics. These exist in separate systems; WarrantyLens may *link* to them by VIN but does not compute them.

### 1.7 Success metrics
- Median reviewer time-per-claim ↓ 40%.
- % claims submitted "evidence-complete" on first try ↑.
- Reviewer agreement rate with high-risk flags (precision proxy).
- Pipeline cost per claim (target < $0.15 at scale).

---

## 2. High-Level Architecture

```
                         ┌──────────────────────────────────────────────┐
                         │                  CLIENTS                       │
                         │  Next.js Web (Reviewer/Admin)  ·  Mechanic PWA │
                         └───────────────┬──────────────────────────────┘
                                         │ HTTPS / JWT
                                         ▼
                         ┌──────────────────────────────────────────────┐
                         │   API Gateway / Reverse Proxy (Nginx/Traefik) │
                         └───────────────┬──────────────────────────────┘
                                         ▼
            ┌────────────────────────────────────────────────────────────────┐
            │                    FastAPI Application (stateless, N replicas)    │
            │  Auth · Claims · Evidence(upload→S3 presigned) · Reports · Admin  │
            │  Enqueues jobs · Serves results · WebSocket/SSE progress          │
            └───┬───────────────┬───────────────┬───────────────┬─────────────┘
                │               │               │               │
                ▼               ▼               ▼               ▼
        ┌────────────┐   ┌────────────┐  ┌────────────┐  ┌──────────────┐
        │ PostgreSQL │   │   Redis    │  │ S3 / MinIO │  │   Qdrant     │
        │ (SoR)      │   │ broker+cache│ │ media+reports│ │ (embeddings) │
        └────────────┘   └─────┬──────┘  └────────────┘  └──────────────┘
                               │ Celery broker
                               ▼
            ┌────────────────────────────────────────────────────────────────┐
            │                       CELERY WORKERS                              │
            │   CPU pool: orchestration, frame extract, PDF, fan-out/fan-in     │
            │   GPU pool: YOLOv11 · Qwen2.5-VL · PaddleOCR · Whisper · BGE-M3   │
            │   (GPU served via Triton/vLLM model server, workers call it)      │
            └────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                  ┌────────────────────────────┐
                  │   GPU Model Server(s)        │
                  │  vLLM (Qwen2.5-VL) ·         │
                  │  Triton (YOLO/OCR/Whisper)   │
                  └────────────────────────────┘
```

**Key separation:** Celery workers are *orchestrators*; the heavy models live behind a **dedicated model server** (vLLM for the VLM, Triton/TorchServe for the rest) so GPUs are pooled, batched, and scaled independently of the orchestration logic. This avoids loading 5 large models into every worker process.

---

## 3. System Architecture Diagram (data flow, per claim)

```
Mechanic                FastAPI            Celery (CPU)        Model Server (GPU)        Stores
   │  create claim ───────►│  insert claim (DRAFT) ─────────────────────────────────────► Postgres
   │  request upload URL ──►│  presigned PUT ───────────────────────────────────────────► S3
   │  PUT video/images ─────────────────────────────────────────────────────────────────► S3
   │  submit claim ────────►│  claim→QUEUED, enqueue pipeline ─────► Redis
   │                        │                          │
   │                        │                  ┌───────▼─────────────────────────────────┐
   │                        │                  │ orchestrator task (chord):               │
   │                        │                  │  1 probe media (ffprobe)                  │
   │                        │                  │  2 frame_extract (ffmpeg, scene+interval) ├──► S3 frames
   │                        │                  │  3 fan-out:                               │
   │                        │                  │     ├ asr_transcribe ───────► Whisper ────┤
   │                        │                  │     ├ yolo_detect (frames) ─► YOLOv11 ────┤──► detections
   │                        │                  │     ├ ocr_extract (frames) ─► PaddleOCR ──┤──► vin/serials
   │                        │                  │     └ vlm_describe (key frames)► Qwen2.5-VL┤──► descriptions
   │                        │                  │  4 fan-in: completeness + risk scoring    │
   │                        │                  │  5 embed evidence ──────────► BGE-M3 ─────┤──► Qdrant
   │                        │                  │  6 report_generate (VLM summarize+PDF) ───┤──► S3 report
   │                        │                  │  7 claim→READY_FOR_REVIEW                 │
   │                        │                  └───────────────────────────────────────────┘
   │  poll/SSE progress ◄───┤◄── status updates (Redis pub/sub → SSE)
Reviewer
   │  open claim ──────────►│  fetch report+evidence (signed URLs) ◄──────────────────────── Postgres/S3
   │  decision + notes ────►│  claim→REVIEWED, write audit ───────────────────────────────► Postgres
```

---

## 4. Database Schema (PostgreSQL)

Conventions: every business table carries `tenant_id` (FK → tenants), `id UUID pk`, `created_at`, `updated_at`. Soft-delete via `deleted_at` where relevant. Money/scores stored as `numeric`. JSONB for flexible AI payloads, but **promote queryable fields to columns**.

### 4.1 Core entities

```sql
-- Tenancy & identity
tenants(id, name, slug, plan, region, settings JSONB, created_at, updated_at)

users(id, tenant_id FK, email UNIQUE-per-tenant, password_hash, full_name,
      role ENUM('admin','reviewer','mechanic'), is_active, last_login_at,
      created_at, updated_at)

-- Optional: refresh token rotation / session revocation
refresh_tokens(id, user_id FK, token_hash, expires_at, revoked_at, user_agent, ip)

audit_logs(id, tenant_id, actor_user_id, action, entity_type, entity_id,
           before JSONB, after JSONB, ip, created_at)   -- append-only

-- Catalog / config (admin-managed)
components(id, tenant_id, code, name, category, parent_id NULL, is_active)
   -- e.g. charging_port, wiring_harness, motor_housing ...

inspection_templates(id, tenant_id, name, version, component_id FK,
                     required_views JSONB, required_evidence JSONB, is_active)
   -- required_views: ['front','left','right','rear','closeup_serial', ...]

fraud_indicator_defs(id, tenant_id, code, label, default_weight, severity, is_active)
   -- impact_damage, crack, scratch, missing_part, corrosion, water_ingress,
   -- tampering, missing_seal, opened_enclosure, non_standard_mod, incomplete

-- Claims
claims(id, tenant_id, claim_number UNIQUE, vin, status ENUM(
         'draft','queued','processing','ready_for_review','reviewed',
         'needs_more_evidence','failed'),
       component_id FK, template_id FK, claim_reason TEXT,
       mechanic_narrative TEXT,
       created_by_user_id FK, assigned_reviewer_id FK NULL,
       completeness_score NUMERIC NULL, risk_score NUMERIC NULL,
       processing_error TEXT NULL,
       submitted_at, processed_at, reviewed_at, created_at, updated_at)

-- Evidence (raw uploads)
media_assets(id, tenant_id, claim_id FK, kind ENUM('video','image'),
             s3_key, content_type, size_bytes, sha256, duration_s NULL,
             width NULL, height NULL, status ENUM('uploaded','processed','rejected'),
             uploaded_by FK, created_at)

-- Derived frames from video
frames(id, tenant_id, claim_id FK, media_asset_id FK, s3_key,
       timestamp_s, frame_index, is_keyframe BOOL, sharpness NUMERIC,
       created_at)

-- AI outputs ------------------------------------------------------------
transcripts(id, claim_id FK, media_asset_id FK, language, full_text TEXT,
            segments JSONB, model_version, created_at)
   -- segments: [{start,end,text,confidence}]

detections(id, tenant_id, claim_id FK, frame_id FK, model_version,
           component_label, defect_label, confidence NUMERIC,
           bbox JSONB, severity NUMERIC NULL, created_at)
   -- one row per detected object/defect on a frame

ocr_results(id, claim_id FK, frame_id FK NULL, media_asset_id FK NULL,
            field_type ENUM('vin','serial','label','other'),
            raw_text, normalized_value, confidence NUMERIC,
            bbox JSONB, model_version, created_at)

vlm_analyses(id, claim_id FK, frame_id FK NULL, prompt_version,
             model_version, description TEXT, findings JSONB,
             raw_response JSONB, created_at)
   -- findings: structured {component, condition, anomalies[], confidence}

embeddings_index(id, claim_id FK, source_type, source_id, qdrant_point_id,
                 model_version, created_at)   -- mirror of vectors stored in Qdrant

-- Scoring & reporting --------------------------------------------------
completeness_checks(id, claim_id FK, template_id FK,
                    required JSONB, present JSONB, missing JSONB,
                    score NUMERIC, created_at)

risk_assessments(id, claim_id FK, score NUMERIC,
                 factors JSONB,         -- [{indicator, weight, evidence_refs, contribution}]
                 model_version, rationale TEXT, created_at)

reports(id, claim_id FK, s3_key_pdf, summary TEXT, payload JSONB,
        generated_by ENUM('system'), version, created_at)

-- Human review --------------------------------------------------------
reviews(id, tenant_id, claim_id FK, reviewer_id FK,
        decision ENUM('approved','rejected','needs_more_evidence','escalated'),
        notes TEXT, overrides JSONB NULL, created_at)
   -- 'decision' is the HUMAN's call; system never writes here.

processing_jobs(id, claim_id FK, celery_task_id, stage, status,
                started_at, finished_at, error TEXT, metrics JSONB, created_at)
```

### 4.2 Key indexes
- `claims (tenant_id, status, created_at)` — queue & dashboard.
- `claims (tenant_id, vin)` — VIN lookups.
- `detections (claim_id)`, `frames (claim_id, media_asset_id)`.
- `ocr_results (claim_id, field_type)`.
- `audit_logs (tenant_id, entity_type, entity_id)`.
- Partial index `claims (assigned_reviewer_id) WHERE status='ready_for_review'`.

### 4.3 Why JSONB + promoted columns
`findings`, `factors`, `segments` evolve with model versions → JSONB keeps schema stable. But `risk_score`, `completeness_score`, `vin`, `status` are filtered/sorted constantly → real columns + indexes.

---

## 5. API Design (REST, versioned under `/api/v1`)

Auth: `Authorization: Bearer <access_jwt>`. All list endpoints paginated (`?page&size`), filterable, tenant-scoped automatically from the token.

### 5.1 Auth
```
POST   /auth/login                {email,password} → {access, refresh, user}
POST   /auth/refresh              {refresh} → {access}
POST   /auth/logout               (revoke refresh)
GET    /auth/me                   → current user
```

### 5.2 Admin / catalog
```
GET/POST/PATCH/DELETE  /users                  (admin)
GET/POST/PATCH         /components             (admin)
GET/POST/PATCH         /inspection-templates   (admin)
GET/POST/PATCH         /fraud-indicators       (admin)
GET                    /audit-logs             (admin)
```

### 5.3 Claims & evidence
```
POST   /claims                         create draft → claim
GET    /claims                         list (filters: status, risk_min, reviewer, vin, date)
GET    /claims/{id}                    detail (joins report, scores, counts)
PATCH  /claims/{id}                    edit narrative/component while draft
POST   /claims/{id}/assign             {reviewer_id}
POST   /claims/{id}/submit             draft → queued (kicks off pipeline)

POST   /claims/{id}/uploads            request presigned URL(s)
          {files:[{filename,content_type,size,kind}]} → {uploads:[{asset_id,url,fields}]}
POST   /claims/{id}/uploads/{asset_id}/complete   confirm + sha256 → marks uploaded

GET    /claims/{id}/evidence           media assets + frames (signed GET urls)
GET    /claims/{id}/status             pipeline status + per-stage progress
GET    /claims/{id}/stream             SSE progress stream
```

### 5.4 AI results & reports
```
GET    /claims/{id}/transcript
GET    /claims/{id}/detections         (filter by frame/defect)
GET    /claims/{id}/ocr                (vin, serials)
GET    /claims/{id}/completeness
GET    /claims/{id}/risk
GET    /claims/{id}/report             metadata + signed PDF url
POST   /claims/{id}/report/regenerate  (admin/reviewer) re-run report stage
```

### 5.5 Review
```
POST   /claims/{id}/review     {decision, notes, overrides?} → review
GET    /claims/{id}/reviews    history
```

### 5.6 Dashboard
```
GET    /dashboard/overview     counts by status, today/week
GET    /dashboard/risk-distribution
GET    /dashboard/completeness-stats
GET    /dashboard/reviewer-queue
```

### 5.7 Conventions
- Errors: RFC 7807 `application/problem+json` `{type,title,status,detail,instance}`.
- Idempotency-Key header on POST /claims and /uploads/complete.
- Rate limits per tenant + per user (Redis token bucket).
- Webhooks (V2): `claim.processed`, `claim.reviewed` for OEM integration.

---

## 6. Backend Folder Structure

```
backend/
├── app/
│   ├── main.py                      # FastAPI app factory, middleware, routers
│   ├── core/
│   │   ├── config.py                # pydantic-settings (env)
│   │   ├── security.py              # jwt, password hashing, deps
│   │   ├── logging.py               # structlog json logging
│   │   ├── tenancy.py               # tenant context middleware
│   │   └── exceptions.py            # problem+json handlers
│   ├── db/
│   │   ├── base.py                  # Declarative base, mixins (TenantMixin, TimestampMixin)
│   │   ├── session.py               # async engine + session
│   │   └── models/                  # SQLAlchemy models (one file per aggregate)
│   ├── schemas/                     # Pydantic v2 request/response DTOs
│   ├── api/
│   │   ├── deps.py                  # get_current_user, require_role, get_tenant
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/           # auth.py claims.py uploads.py reviews.py admin.py dashboard.py reports.py
│   ├── services/                    # business logic (no FastAPI imports)
│   │   ├── claim_service.py
│   │   ├── evidence_service.py
│   │   ├── storage_service.py       # S3 presign, put/get
│   │   ├── completeness_service.py
│   │   ├── risk_service.py
│   │   └── report_service.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   ├── orchestrator.py          # chord/chain pipeline definition
│   │   └── tasks/
│   │       ├── frames.py            # ffmpeg extraction
│   │       ├── asr.py               # whisper client
│   │       ├── detection.py         # yolo client
│   │       ├── ocr.py               # paddleocr client + VIN/serial parsing
│   │       ├── vlm.py               # qwen2.5-vl client
│   │       ├── embed.py             # bge-m3 + qdrant upsert
│   │       └── report.py
│   ├── ml/
│   │   ├── clients/                 # thin HTTP/grpc clients to model server
│   │   │   ├── triton_client.py
│   │   │   └── vllm_client.py
│   │   ├── postprocess/             # nms, vin_checksum, serial_regex, scene_select
│   │   └── prompts/                 # versioned VLM prompt templates
│   └── integrations/                # webhooks, OEM connectors (V2)
├── alembic/                         # migrations
├── tests/                           # pytest (unit + integration w/ testcontainers)
├── pyproject.toml
├── Dockerfile
└── Dockerfile.worker
```

**Rule:** `services/` and `ml/` never import FastAPI; they're callable from both API and Celery. Endpoints are thin.

---

## 7. Frontend Folder Structure (Next.js App Router)

```
frontend/
├── app/
│   ├── (auth)/login/page.tsx
│   ├── (app)/
│   │   ├── layout.tsx                # shell: sidebar, role-aware nav
│   │   ├── dashboard/page.tsx
│   │   ├── claims/
│   │   │   ├── page.tsx              # list + filters (reviewer queue)
│   │   │   ├── new/page.tsx          # mechanic create
│   │   │   └── [id]/
│   │   │       ├── page.tsx          # claim detail
│   │   │       ├── evidence/page.tsx # media + frame viewer w/ bbox overlay
│   │   │       └── review/page.tsx   # decision panel
│   │   └── admin/
│   │       ├── users/page.tsx
│   │       ├── components/page.tsx
│   │       └── templates/page.tsx
│   └── api/                          # route handlers (BFF proxy if needed)
├── components/
│   ├── ui/                           # shadcn primitives
│   ├── claims/                       # ClaimTable, RiskBadge, CompletenessGauge
│   ├── evidence/                     # VideoPlayer, FrameGrid, BBoxOverlay, TranscriptPanel
│   ├── upload/                       # Dropzone, MultipartUploader (resumable)
│   └── charts/                       # RiskDistribution, StatusBreakdown
├── lib/
│   ├── api/                          # typed client (generated from OpenAPI), react-query hooks
│   ├── auth/                         # session, token refresh, route guards
│   └── utils/
├── hooks/                            # useClaimStatus (SSE), useUpload
├── types/                            # generated from backend OpenAPI
├── package.json
└── Dockerfile
```

- **State/data:** React Query for server state; minimal client state. Types generated from the backend OpenAPI schema (`openapi-typescript`) so frontend and backend never drift.
- **Real-time:** `useClaimStatus` subscribes to `/claims/{id}/stream` (SSE) for pipeline progress.
- **Auth:** access token in memory, refresh in httpOnly cookie; middleware-based route protection by role.

---

## 8. AI Pipeline Design

The pipeline is a Celery **chord**: a parallel group (fan-out) followed by a callback (fan-in). Orchestrated in `workers/orchestrator.py`.

```
submit → orchestrate_claim(claim_id):
  chain(
    probe_media,                       # ffprobe: duration, resolution, codec, sanity
    extract_frames,                    # scene-change + fixed interval, dedup, sharpness filter
    group(                             # FAN-OUT (parallel)
        transcribe_audio,              # Whisper → transcript
        detect_objects,                # YOLOv11 over selected frames → detections
        run_ocr,                       # PaddleOCR over high-text frames → vin/serials
        describe_keyframes,            # Qwen2.5-VL over keyframes → structured findings
    ),
    score_and_assemble,                # FAN-IN: completeness + risk + embed
    generate_report,
    finalize,                          # status → ready_for_review, notify
  )
```

### 8.1 Frame extraction strategy
- Two sources of frames: **scene-change detection** (ffmpeg `select='gt(scene,0.3)'`) + **fixed interval** (e.g. 1 fps) to guarantee coverage.
- Drop near-duplicates (perceptual hash) and blurry frames (variance of Laplacian < threshold).
- Cap frames per claim (e.g. ≤ 120) to bound GPU cost; prioritize sharp, high-information frames.
- Mark `is_keyframe` for the subset sent to the expensive VLM (e.g. ≤ 24 best frames + frames where YOLO found defects/labels).

### 8.2 Model routing (cost-tiered)
1. **YOLOv11** runs on all selected frames (cheap, fast) → locates components + candidate defects + label/sticker regions.
2. **PaddleOCR** runs only on frames where YOLO (or a text detector) found label/sticker regions → VIN & serials.
3. **Qwen2.5-VL** runs only on keyframes + frames with YOLO defect hits → rich condition description, anomaly reasoning, and cross-check ("does the spoken narrative match what's visible?").
4. **Whisper** runs once per audio track.
5. **BGE-M3** embeds transcript chunks + VLM findings + claim text → Qdrant for semantic search & similar-claim retrieval.

This routing means most frames never touch the VLM — the dominant cost — cutting per-claim GPU spend dramatically.

### 8.3 Completeness scoring
Compare `inspection_template.required_views/evidence` against what's actually present:
- Required views detected? (e.g., did YOLO/VLM see front, both sides, rear, serial close-up?)
- VIN present & checksum-valid?
- Component-specific serials present?
- Audio narrative present & on-topic?
- Minimum frame coverage / duration met?

`completeness_score = weighted fraction satisfied`. Output a concrete **missing-evidence list** (the most actionable artifact for the mechanic).

### 8.4 Risk scoring (explainable, never "fraud")
Weighted sum of normalized indicators, each linked to evidence:
```
risk_score = Σ wᵢ · severityᵢ        (normalized 0–100)
factors = [
  {indicator:'water_ingress', weight, severity, evidence_refs:[frame_id,detection_id], contribution},
  {indicator:'opened_enclosure', ...},
  {indicator:'narrative_image_mismatch', ...},   # from VLM cross-check
  {indicator:'incomplete_inspection', ...},      # from completeness
]
rationale = VLM-generated plain-language summary citing the factors.
```
Weights come from `fraud_indicator_defs` (admin-tunable per tenant). **MVP = transparent rule/heuristic engine**, not a black-box classifier — reviewers must understand *why*. (A learned re-ranker is a V2 option, only with explainability + human labels.)

### 8.5 Model & prompt versioning
Every AI row stores `model_version` / `prompt_version`. Prompts live in `ml/prompts/` and are versioned. This makes results reproducible and lets us A/B and roll back.

### 8.6 Failure handling
- Each stage retries with backoff (idempotent; writes keyed by claim+stage).
- Partial failure is allowed: if VLM fails, claim can still go to review flagged "partial AI" rather than blocking. `processing_jobs` records per-stage status.
- A claim only becomes `failed` if a *critical* early stage (probe/frames) fails.

---

## 9. Object Detection Pipeline (YOLOv11 detail)

- **Classes (two heads / two-stage):** (a) *component* classes (charging_port, wiring_harness, motor_housing, …) and (b) *defect/indicator* classes (crack, scratch, impact_dent, corrosion, missing_seal, tamper_mark, broken, water_stain). Modeling choice: one multi-class model with combined classes, or component-localizer + defect-classifier crop pipeline. **Recommend two-stage** for MVP: detect/locate component region → crop → defect classifier — better data efficiency with small datasets.
- **Serving:** Triton Inference Server, dynamic batching, FP16. Workers send frame batches, get boxes back.
- **Post-process:** class-aware NMS, confidence thresholds per class (tunable), map boxes → component → feed defects into risk engine with `severity` from box size × confidence × class weight.
- **Cold-start data problem (honest):** we won't have a labeled EV-defect dataset on day one. Bootstrapping plan:
  1. MVP leans on **Qwen2.5-VL zero/few-shot** for damage *description*, with YOLO trained on whatever we can label (transfer from generic damage datasets — car scratch/dent datasets exist).
  2. Use the platform itself as a **labeling flywheel**: reviewer confirmations/overrides become labels → periodic YOLO fine-tunes (active learning on low-confidence frames).
  3. Track per-class precision/recall; promote YOLO over VLM for a class only once it beats the VLM baseline.
- **Eval:** mAP@0.5 per class, plus reviewer-agreement on flagged defects.

---

## 10. OCR Pipeline (VIN + serials)

```
candidate frames (YOLO label/sticker regions OR text-dense frames)
  → PaddleOCR (det+rec) → raw tokens + boxes
  → field classification:
       VIN parser:  17-char, exclude I/O/Q, ISO-3779 checksum (pos 9) validation
       Serial parser: per-component regex from components catalog
  → normalize (uppercase, strip), dedupe across frames, pick highest-confidence
  → confidence: OCR conf × checksum_valid × cross-frame_agreement
  → store ocr_results; reconcile VIN against claim.vin (match / mismatch → risk factor)
```
- **VIN cross-check** is a high-value signal: VIN on the label vs. VIN entered on the claim mismatch → strong evidence/risk indicator (and a completeness gate).
- Multi-frame voting reduces single-frame OCR errors.
- PaddleOCR served on GPU (or CPU if throughput allows — it's relatively light).

---

## 11. Report Generation Pipeline

```
inputs: detections, ocr_results, transcript, vlm_analyses, completeness, risk
  → assemble structured ReportPayload (JSONB):
       header (claim, VIN, component, dates, mechanic)
       evidence_index (media + key frames thumbnails)
       damage_summary (grouped defects w/ frame refs + severity)
       missing_evidence (from completeness)
       transcript_highlights
       risk_panel (score + factors + rationale, with EVIDENCE LINKS)
       disclaimer ("advisory; final decision is the reviewer's")
  → VLM (Qwen2.5-VL/LLM) writes the narrative summary from the structured payload
       (grounded: it summarizes provided findings, does NOT invent; temperature low)
  → render: HTML template → PDF (WeasyPrint or Playwright-to-PDF) with embedded thumbnails
  → upload PDF to S3, store reports row, signed URL on demand
```
- Report is **regenerable** and **versioned** — re-running models produces a new report version, never silently overwrites.
- Every claim in the damage summary and risk panel deep-links back to the frame/detection that produced it (auditability).

---

## 12. Authentication Design

- **Scheme:** JWT access (short-lived, ~15 min) + refresh (rotating, ~7 days, stored hashed in `refresh_tokens`, revocable). Refresh in httpOnly+Secure cookie; access in memory on the client.
- **Passwords:** Argon2id (or bcrypt) hashing.
- **RBAC:** roles `admin | reviewer | mechanic`; enforced via FastAPI dependency `require_role(...)`. Resource-level checks ensure tenant isolation (a user can only touch their tenant's rows — enforced in a query-time tenant filter, not just in code).
- **Multi-tenant:** `tenant_id` resolved from the JWT claim; a middleware sets a tenant context used by the repository layer to scope every query. (Optionally Postgres RLS as defense-in-depth.)
- **Service-to-service:** workers use an internal service token / network isolation, not user JWTs.
- **V2:** SSO/OIDC (OEM IdPs), SCIM provisioning, MFA for admins, API keys for OEM system integration.

---

## 13. Security Architecture

- **Transport:** TLS everywhere; HSTS. Internal traffic on a private network/VPC.
- **At rest:** S3 SSE, Postgres encrypted volumes, secrets in a secret manager (not env files in prod).
- **Media access:** never public; **short-lived presigned URLs** for both upload and download. Uploads constrained by content-type + size + (V2) AV scan + content-type sniff.
- **Tenant isolation:** enforced at query layer + tested; optional Postgres RLS.
- **Audit immutability:** `audit_logs` append-only (no UPDATE/DELETE grants); covers logins, claim transitions, reviews, admin changes, report regen.
- **Input safety:** validate/transcode uploaded media in a sandboxed worker (ffmpeg in a restricted container) — never trust client metadata; re-derive duration/dimensions/sha256 server-side.
- **PII:** VIN is PII-adjacent; faces/plates may appear → V2 auto-blur before reviewer display + redacted report mode. Retention policy + per-tenant data deletion (GDPR/CCPA-style).
- **AppSec:** rate limiting, CORS allowlist, dependency scanning, OWASP top-10 review, signed webhooks (HMAC).
- **Model safety:** VLM prompts pinned & reviewed to prevent the model from emitting "fraud"/legal-conclusion language; output post-filtered for prohibited determinations.
- **LLM hosting:** Qwen2.5-VL / Whisper / etc. are **self-hosted open models** — no inspection media leaves our infra to a third-party API. This is a selling point to OEMs (data control).

---

## 14. Scalability Plan

| Layer | Scale strategy |
|---|---|
| API | Stateless → horizontal autoscale behind LB; HPA on CPU/RPS |
| Postgres | Vertical first; read replicas for dashboard/analytics; partition `frames`/`detections` by month at high volume; PgBouncer pooling |
| Redis | Managed Redis; separate instances for broker vs cache |
| Celery | Two queues: `cpu` (frame extract, PDF, orchestration) and `gpu` (model calls). Scale pools independently. Priority queue for SLA claims |
| Model server | vLLM/Triton with dynamic batching; autoscale GPU replicas on queue depth; model-level batching amortizes GPU |
| Qdrant | Clustered/sharded at scale; HNSW params tuned per collection |
| S3 | Effectively infinite; lifecycle rules tier old media to cold storage |
| Media transfer | Direct browser→S3 via presigned (API never proxies bytes) |

- **Backpressure:** if GPU queue depth exceeds threshold, claims stay `queued` (visible to user as "in line") rather than overloading; SLA-tier claims jump the queue.
- **Bottleneck reality:** GPU is the scaling unit. Plan capacity by `claims/day × GPU-seconds/claim`. Batching keyframes across claims is the biggest lever.

---

## 15. Cost Estimates (order-of-magnitude, self-hosted)

Assume one mid claim = 2-min video → ~80 frames kept, ~24 to VLM, 1 audio pass.

**Per-claim GPU compute (rough):**
- Whisper (2 min audio): ~2–4 GPU-s
- YOLOv11 (80 frames batched): ~1–2 GPU-s
- PaddleOCR (~15 frames): ~1–2 GPU-s
- Qwen2.5-VL (24 keyframes + report summary): ~30–60 GPU-s (dominant)
- BGE-M3 embeddings: <1 GPU-s
- **≈ 40–70 GPU-seconds/claim.**

On a single rented L4/A10 (~$0.6–1.0/hr): ~50–90 claims/GPU-hour → **~$0.01–0.02 GPU cost/claim**. Add storage + DB + egress + overhead → realistic **all-in $0.05–0.15/claim** at modest scale. The VLM frame budget is the cost knob.

**Monthly infra, MVP / early (illustrative):**
| Item | Est. /mo |
|---|---|
| 1× GPU instance (L4/A10, on-demand or spot) | $300–700 |
| App + worker compute (2–3 small nodes) | $150–300 |
| Managed Postgres (small HA) | $100–250 |
| Redis (managed small) | $50–100 |
| S3 storage + egress (depends on volume) | $50–300 |
| Qdrant (small) | $50–150 |
| **Total** | **~$700–1,800/mo** |

Spot GPUs + batching + scale-to-zero on the GPU pool during off-hours cut this substantially. At 10k claims/day (V2) the model scales linearly with GPU replicas; cost/claim *drops* with better batching.

---

## 16. GPU Requirements

- **Dominant consumer:** Qwen2.5-VL. The 7B-class VLM in FP16 needs ~16–20 GB VRAM (more for longer context / multi-image); served via vLLM with paged attention + batching. A **24 GB GPU (L4 / A10 / RTX 4090 / A5000)** comfortably hosts the 7B VLM. For the 3B variant, 12–16 GB suffices.
- **Co-residency:** YOLOv11 (~1–3 GB), PaddleOCR (~1–2 GB), Whisper (small/medium ~1–3 GB), BGE-M3 (~2 GB) can share a GPU with headroom on a 24 GB card for MVP, or run on a second cheaper GPU/CPU.
- **MVP recommendation:** 1× 24 GB GPU (VLM via vLLM) + the lighter models on the same card or CPU. **Scale-out:** dedicate GPU(s) to the VLM via Triton/vLLM, separate pool for detection/OCR/ASR.
- **Dev note (founder's local box):** the local GTX 1650 Ti (4 GB) is **not** sufficient for the 7B VLM — use it for YOLO/OCR/Whisper-small dev and a quantized/3B VLM or a cloud GPU for VLM development. Production VLM = cloud GPU.
- **Optimization levers:** FP16/INT8 quantization (AWQ/GPTQ for the VLM), dynamic batching, capped keyframe count, frame dedup, model warm-pools to avoid cold loads.

---

## 17. Docker Architecture

```
docker-compose.yml (dev / single-host)
├── nginx                 # reverse proxy, TLS termination
├── api                   # FastAPI (uvicorn/gunicorn)
├── worker-cpu            # Celery: frames, pdf, orchestration
├── worker-gpu            # Celery: calls model server (or hosts light models)
├── model-server          # vLLM (Qwen2.5-VL) [+ Triton for YOLO/OCR/Whisper]
├── beat                  # Celery beat (scheduled cleanup, retries)
├── postgres
├── redis
├── qdrant
├── minio                 # S3-compatible (dev)
└── frontend              # Next.js
```

- Separate `Dockerfile` (api/worker, slim python) and `Dockerfile.gpu` (CUDA base + torch + models).
- Multi-stage builds; pinned deps; non-root users; healthchecks on every service.
- Models baked into the model-server image or pulled from a model registry/volume at boot (cached).
- `.env` per environment; secrets injected, never committed.

---

## 18. Deployment Architecture

- **MVP:** single cloud (AWS/GCP) — managed Postgres, managed Redis, object storage, one GPU instance for the model server, container runtime for API/workers (ECS/Fargate or a small k8s). Qdrant managed or self-hosted.
- **Scale:** Kubernetes:
  - API Deployment + HPA, Ingress + cert-manager TLS.
  - Celery CPU & GPU worker Deployments (separate node pools; GPU pool with NVIDIA device plugin, taints/tolerations).
  - Model server as its own Deployment on GPU nodes (vLLM/Triton), autoscaled on queue depth (KEDA on Redis queue length).
  - Stateful: managed Postgres + Redis + S3; Qdrant StatefulSet or managed.
- **CI/CD:** GitHub Actions → lint/test (testcontainers) → build & scan images → push registry → deploy (staging → prod, manual gate). Alembic migrations run as a pre-deploy job.
- **Environments:** dev (compose) · staging · prod. Feature flags for risky AI changes.
- **Observability:** Prometheus + Grafana (API latency, queue depth, GPU util, per-stage pipeline timings, cost/claim), structured JSON logs → Loki, Sentry for errors, OpenTelemetry traces across API→Celery→model server.
- **DR:** Postgres PITR + cross-region backup; S3 versioning + replication; documented RTO/RPO.

---

## 19. Development Roadmap (phased)

**Phase 0 — Foundations (Week 1):** Repos, Docker compose, CI, Postgres+Alembic, auth + tenancy, base models/migrations, OpenAPI→TS codegen. *Exit:* login works, multi-tenant scaffolding, health checks green.

**Phase 1 — Claims & Evidence (Weeks 2–3):** Claim CRUD, presigned upload (resumable video), media ingestion + ffprobe + sha256, frame extraction worker, S3/MinIO wiring. *Exit:* a mechanic can create a claim and upload media; frames appear.

**Phase 2 — AI Pipeline core (Weeks 3–5):** Model server (vLLM + Triton) up; Whisper, YOLOv11, PaddleOCR, Qwen2.5-VL clients; Celery chord orchestration; persist transcripts/detections/ocr/vlm. *Exit:* submitting a claim runs the full pipeline end-to-end and stores AI outputs.

**Phase 3 — Scoring & Reports (Weeks 5–6):** Completeness engine, explainable risk engine, BGE-M3 + Qdrant, report assembly + PDF, regeneration. *Exit:* claim reaches `ready_for_review` with a downloadable report + risk panel.

**Phase 4 — Review & Dashboard (Weeks 6–7):** Reviewer queue, claim detail, evidence viewer with bbox overlay + transcript, decision flow + audit, dashboard charts. *Exit:* reviewer can work a queue and decide; metrics visible.

**Phase 5 — Hardening (Weeks 7–8):** Security pass, rate limits, observability, load test, cost dashboards, docs, seed data, demo tenant. *Exit:* MVP deployable to staging, demo-ready.

(8-week MVP for a small team. Compresses with parallel FE/BE work.)

---

## 20. Sprint Plan (2-week sprints)

**Sprint 1 — Foundation & Auth**
- BE: project scaffold, config, DB, Alembic, User/Tenant models, JWT auth, RBAC deps, audit log infra.
- FE: app shell, login, role-aware nav, API client + auth refresh.
- Infra: compose (pg/redis/minio/qdrant), CI lint+test.
- *Deliverable:* authed multi-tenant skeleton.

**Sprint 2 — Claims & Evidence**
- BE: claim CRUD, components/templates catalog, presigned uploads + complete, media ingestion, frame extraction task.
- FE: claim create (mechanic), upload dropzone w/ multipart + progress, claim list.
- *Deliverable:* create claim + upload + frames extracted.

**Sprint 3 — AI Pipeline**
- BE: model server deploy, ML clients, Celery chord, ASR/YOLO/OCR/VLM tasks, persistence, SSE status.
- FE: pipeline progress UI, evidence viewer (frames, transcript).
- *Deliverable:* full AI pipeline end-to-end.

**Sprint 4 — Scoring, Reports, Review, Dashboard**
- BE: completeness + risk engines, embeddings/Qdrant, report+PDF, review endpoint, dashboard aggregates.
- FE: risk/completeness panels, bbox overlay, decision flow, dashboard charts, PDF download.
- *Deliverable:* reviewer-complete loop + MVP dashboard.

**Sprint 5 — Hardening & Launch**
- Security, observability, load/cost testing, docs, demo seed, staging deploy.
- *Deliverable:* demo-ready MVP.

---

## 21. Risk Analysis

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| No labeled EV-defect dataset at start | YOLO weak early | High | VLM-first for description; transfer-learn from car-damage datasets; labeling flywheel from reviewer feedback; report per-class metrics honestly |
| GPU cost runs away | Margin death | Med | Cost-tiered routing (most frames skip VLM), keyframe cap, batching, spot GPUs, per-claim cost dashboard |
| VLM hallucination / inventing damage | Wrong risk flags, trust loss | Med | Grounded prompts (summarize provided findings only), low temp, cross-check vs YOLO/OCR, evidence-linked factors, human-in-loop |
| Model emits "fraud"/legal conclusions | Legal/liability | Med | Prompt constraints + output post-filter; never store `is_fraud`; advisory-only UI + disclaimer |
| Large-video upload reliability | Bad mechanic UX | Med | Resumable multipart, direct-to-S3, client retries, server-side validation |
| Pipeline partial failures block claims | Throughput | Med | Per-stage idempotent retries; allow partial results; `failed` only on critical stages |
| Tenant data leakage | Catastrophic (OEM trust) | Low | Query-layer tenant scoping + tests + optional RLS; signed URLs; audit |
| PII (faces/plates) exposure | Compliance | Med | V2 auto-blur, retention policy, region pinning |
| Model/prompt drift breaks reproducibility | Audit gaps | Med | Version every output; pinned prompts; regenerable reports |
| Scope creep into battery/telemetry | Dilution | Med | Hard scope boundary in PRD; link by VIN only |
| Reviewer distrust of AI | Low adoption | Med | Explainability-first, evidence links, measure agreement, let admins tune weights |

---

## 22. MVP Definition

**In:** multi-tenant auth + RBAC; claim create + resumable evidence upload; full AI pipeline (frames, Whisper ASR, YOLOv11 detection, PaddleOCR VIN/serial, Qwen2.5-VL description); explainable completeness + risk scoring; BGE-M3/Qdrant embeddings; PDF report (regenerable, evidence-linked); reviewer queue + claim detail + evidence viewer with bbox overlay + decision/notes + audit; dashboard (status, pending, risk distribution, completeness); self-hosted models; observability + security baseline; deployable to staging.

**Out (deferred):** learned risk classifier, face/plate blur, SSO/MFA/SCIM, OEM webhooks/connectors, mobile-native app, multi-language UI, advanced analytics, active-learning retraining UI, A/B prompt framework.

**MVP done when:** a mechanic submits a real video+image claim, the pipeline produces an evidence-linked report with completeness + explainable risk in ≤ 8 min p95, and a reviewer triages the queue and records a decision with full audit — multi-tenant, secure, observable, on staging.

---

## 23. Version 2 Roadmap

1. **Labeling flywheel & active learning** — reviewer confirmations → training labels; scheduled YOLO/defect-classifier fine-tunes; per-class promotion gating.
2. **Learned, explainable risk re-ranker** — supervised on human decisions, with SHAP-style attributions; still advisory.
3. **PII protection** — auto face/plate blur, redacted report mode, retention automation.
4. **Enterprise auth** — OIDC SSO, MFA, SCIM, API keys.
5. **OEM integrations** — webhooks (`claim.processed/reviewed`), warranty-system connectors, bulk import/export.
6. **Mechanic mobile app / PWA** — guided capture with on-device completeness hints (capture the missing view *before* leaving the bay).
7. **Similar-claim retrieval** — Qdrant-powered "claims like this" for reviewers (fraud-ring patterns, repeated VINs).
8. **Analytics suite** — defect hot-spots by component/model/region, completeness trends, reviewer throughput.
9. **Multi-region / data residency**, **SOC2**, **fine-grained cost & SLA tiers**.
10. **Model upgrades** — newer/larger VLMs, quantization, on-device edge inference for capture-time hints.

---

## 24. Production Readiness Checklist

**Reliability**
- [ ] Health/readiness probes on all services
- [ ] Idempotent, retrying pipeline stages; partial-failure handling
- [ ] Graceful shutdown / task draining
- [ ] Load tested at target claims/day; backpressure verified

**Data**
- [ ] Alembic migrations reversible & CI-tested
- [ ] Postgres PITR + tested restore; S3 versioning + replication
- [ ] Retention & deletion policies implemented per tenant

**Security**
- [ ] TLS everywhere, HSTS; secrets in secret manager
- [ ] Tenant isolation tested (incl. negative tests); optional RLS
- [ ] Presigned URLs only; upload validation + size/type limits
- [ ] Audit log append-only & covering all mutations
- [ ] Dependency + image scanning in CI; OWASP review
- [ ] VLM output filter blocks fraud/legal-conclusion language

**Observability**
- [ ] Metrics (latency, queue depth, GPU util, per-stage timing, cost/claim)
- [ ] Centralized logs + traces; Sentry alerts
- [ ] Dashboards + on-call alerting + runbooks

**AI quality**
- [ ] Per-class detection metrics tracked; eval set maintained
- [ ] Model/prompt versions recorded on every output; rollback path
- [ ] Reviewer-agreement metric instrumented
- [ ] Reports reproducible/regenerable

**Compliance / product**
- [ ] "Advisory only / human decides" disclaimer in UI + reports
- [ ] No `is_fraud` anywhere; only risk indicators
- [ ] Data residency & PII handling documented
- [ ] Terms covering AI assistance & liability

**Ops**
- [ ] CI/CD with staging gate; migration pre-deploy job
- [ ] Rollback procedure; DR runbook with RTO/RPO
- [ ] Cost monitoring + budget alerts (GPU especially)
- [ ] Seed/demo tenant + docs

---

## Appendix A — Claim State Machine

```
draft ──submit──► queued ──worker pick──► processing
processing ──success──► ready_for_review
processing ──critical failure──► failed ──retry──► queued
ready_for_review ──reviewer──► reviewed
ready_for_review ──reviewer──► needs_more_evidence ──new upload──► queued
```

## Appendix B — Tech Stack Summary
- **AI:** Qwen2.5-VL (VLM, vLLM), YOLOv11 (detection, Triton), PaddleOCR (OCR), Whisper (ASR), BGE-M3 (embeddings), Qdrant (vectors).
- **Backend:** Python, FastAPI, SQLAlchemy (async), Alembic, PostgreSQL, Redis, Celery, Docker.
- **Frontend:** Next.js, TypeScript, TailwindCSS, ShadCN UI, React Query.
- **Storage:** S3-compatible (MinIO dev / S3 prod).
- **Infra:** Nginx/Traefik, Kubernetes (scale), Prometheus/Grafana/Loki/Sentry/OTel.
```
