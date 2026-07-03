# WarrantyLens — Production Readiness Checklist

Status as of Sprint 5. ✅ done · ◑ partial · ☐ todo. See ARCHITECTURE.md §24 for the
full target checklist; this tracks the actual build.

## Security
- ✅ JWT access + rotating/revocable refresh tokens; Argon2 hashing
- ✅ RBAC (`require_role`) + per-tenant query scoping on every read
- ✅ Security headers (nosniff, X-Frame-Options DENY, Referrer-Policy, HSTS in prod)
- ✅ Rate limiting (Redis fixed-window, stricter on `/auth`, fail-open)
- ✅ Upload validation (content-type allowlist + size cap); presigned URLs only (bytes never proxied)
- ✅ Append-only audit log on logins, claim transitions, reviews, admin changes
- ✅ Prod startup guard: refuses to boot with default JWT secret / DEBUG / default S3 creds
- ✅ Self-hosted models (no inspection media leaves infra)
- ◑ CORS allowlist (configurable) — set real origins per env
- ☐ Secrets in a managed secret store (currently env)
- ☐ AV scan on uploads; face/plate blur (V2)
- ☐ Postgres RLS as defense-in-depth (query-layer scoping in place)

## Reliability
- ✅ Healthchecks: `/api/v1/health`, `/api/v1/health/db`; container HEALTHCHECK
- ✅ Per-stage `ProcessingJob` tracking; AI stages tolerate partial failure
- ✅ Critical-stage failure → claim `failed` + `processing_error`
- ✅ Idempotent submit gate (requires uploaded evidence)
- ☐ Load test at target claims/day; backpressure on GPU queue depth (KEDA)

## Observability
- ✅ Prometheus `/metrics` (request count + latency histogram + rate-limited counter)
- ✅ Structured JSON access logs with per-request `X-Request-ID`
- ◑ Dashboards/alerting (metrics exposed; Grafana/alerts not wired)
- ☐ Distributed tracing (OpenTelemetry across API→Celery→model server)
- ☐ Sentry error reporting

## Data
- ✅ Alembic migrations (0001–0004), reversible, CI-applied
- ☐ Postgres PITR + tested restore; S3 versioning/replication
- ☐ Retention + per-tenant deletion policy

## Deployment
- ✅ Gunicorn + Uvicorn workers (prod CMD); slim multi-stage image; non-root user
- ✅ Separate worker image (`Dockerfile.worker`, ffmpeg) + queue
- ✅ docker-compose full stack; GitHub Actions CI (lint + migrate + pytest + FE build)
- ☐ Kubernetes manifests / HPA / KEDA; staging→prod gate; DR runbook

## AI quality & compliance
- ✅ Advisory-only: no `is_fraud` anywhere; risk = evidence-linked factors; "human decides" in UI + report
- ✅ VLM prompt constrained against fraud/legal conclusions; model/prompt versions recorded
- ✅ Reports reproducible/regenerable + versioned
- ☐ Per-class detection metrics + eval set (needs fine-tuned YOLO + labels)
- ☐ Reviewer-agreement metric instrumented

## Pre-launch must-dos
1. Generate real `JWT_SECRET`; set `ENVIRONMENT=production`, `DEBUG=false`.
2. Real S3 + Postgres + Redis credentials in a secret manager.
3. Set CORS origins to the real frontend domain.
4. Run `alembic upgrade head` + seed tenant; smoke-test an end-to-end claim.
5. Stand up the GPU model host (vLLM) or Ollama; set AI flags.
6. Wire Grafana dashboards + alerts on `/metrics`; add Sentry DSN.
