"""End-to-end smoke test — proves the whole stack is wired together.

Run it INSIDE the api container (so presigned MinIO URLs resolve):
    docker compose exec api python -m app.scripts.smoke_test

It drives a real claim through every layer:
  login → create claim → presigned upload → PUT to S3 → complete → submit
  → pipeline (frame/scoring/report) → risk/completeness/report → review → dashboard

AI models may be off (stages skip cleanly) — this verifies wiring, not model quality.
Exits non-zero on the first failed step.
"""
from __future__ import annotations

import io
import sys
import time

import httpx
from PIL import Image

from app.core.config import settings

BASE = "http://localhost:8000/api/v1"
PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_n = 0


def step(ok: bool, label: str, detail: str = "") -> None:
    global _n
    _n += 1
    print(f"  [{_n:02d}] {PASS if ok else FAIL}  {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        print("\nSMOKE TEST FAILED.")
        sys.exit(1)


def _test_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (90, 110, 130)).save(buf, format="JPEG")
    return buf.getvalue()


def main() -> None:
    print("WarrantyLens smoke test\n")
    c = httpx.Client(timeout=30)

    # 1) Health
    r = c.get(f"{BASE}/health")
    step(r.status_code == 200 and r.json().get("status") == "ok", "API health")
    rdb = c.get(f"{BASE}/health/db")
    step(rdb.status_code == 200, "Database reachable")

    # 2) Login (seeded admin)
    r = c.post(f"{BASE}/auth/login", json={
        "email": settings.seed_admin_email, "password": settings.seed_admin_password,
    })
    step(r.status_code == 200, "Login as seeded admin", r.text[:120] if r.status_code != 200 else "")
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # 3) Create claim
    r = c.post(f"{BASE}/claims", headers=h, json={
        "vin": "1HGBH41JXMN109186", "claim_reason": "smoke test claim",
        "mechanic_narrative": "front panel inspection",
    })
    step(r.status_code == 201, "Create claim")
    claim_id = r.json()["id"]

    # 4) Request presigned upload
    r = c.post(f"{BASE}/claims/{claim_id}/uploads", headers=h, json={
        "files": [{"filename": "front.jpg", "content_type": "image/jpeg",
                   "kind": "image", "size": 12345}],
    })
    step(r.status_code == 200, "Request presigned upload URL")
    slot = r.json()["uploads"][0]

    # 5) PUT bytes directly to S3/MinIO
    img = _test_jpeg()
    put = httpx.put(slot["upload_url"], content=img, headers={"Content-Type": "image/jpeg"}, timeout=30)
    step(put.status_code in (200, 204), "PUT image to object storage", f"status {put.status_code}")

    # 6) Complete upload (server verifies via head_object)
    r = c.post(f"{BASE}/claims/{claim_id}/uploads/{slot['asset_id']}/complete",
               headers=h, json={"sha256": None})
    step(r.status_code == 200 and r.json()["status"] == "uploaded", "Complete upload (verified in storage)")

    # 7) Submit → kicks the pipeline
    r = c.post(f"{BASE}/claims/{claim_id}/submit", headers=h)
    step(r.status_code == 200 and r.json()["status"] in ("queued", "processing"),
         "Submit claim (pipeline enqueued)")

    # 8) Poll until processed
    final = None
    for _ in range(60):
        s = c.get(f"{BASE}/claims/{claim_id}/status", headers=h).json()
        if s["status"] in ("ready_for_review", "reviewed", "needs_more_evidence", "failed"):
            final = s
            break
        time.sleep(2)
    step(final is not None and final["status"] != "failed",
         "Pipeline finished", f"status={final['status'] if final else 'timeout'}; "
         f"stages={[(x['stage'], x['status']) for x in (final or {}).get('stages', [])]}")

    # 9) Scoring + report present
    comp = c.get(f"{BASE}/claims/{claim_id}/completeness", headers=h)
    step(comp.status_code == 200 and comp.json() is not None, "Completeness computed",
         f"score={comp.json().get('score') if comp.json() else None}")
    risk = c.get(f"{BASE}/claims/{claim_id}/risk", headers=h)
    step(risk.status_code == 200 and risk.json() is not None, "Risk assessment computed",
         f"score={risk.json().get('score') if risk.json() else None}")
    rep = c.get(f"{BASE}/claims/{claim_id}/report", headers=h)
    step(rep.status_code == 200 and rep.json() is not None, "Report generated",
         f"v{rep.json().get('version')}, pdf={'yes' if rep.json().get('pdf_url') else 'html-only'}")

    # 10) Human review
    r = c.post(f"{BASE}/claims/{claim_id}/review", headers=h,
               json={"decision": "approved", "notes": "smoke test approval"})
    step(r.status_code == 201, "Record reviewer decision")
    r = c.get(f"{BASE}/claims/{claim_id}", headers=h)
    step(r.json()["status"] == "reviewed", "Claim transitioned to reviewed")

    # 11) Dashboard aggregates
    r = c.get(f"{BASE}/dashboard/overview", headers=h)
    step(r.status_code == 200 and r.json()["total"] >= 1, "Dashboard overview")

    print(f"\n\033[32mALL {_n} STEPS PASSED — the stack is fully wired.\033[0m")


if __name__ == "__main__":
    main()
