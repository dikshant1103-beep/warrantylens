"""Push a REAL damage image through the live pipeline and confirm the fine-tuned
YOLO detector fires. Run inside the api container:
    docker compose exec -T api python -m app.scripts.verify_yolo /tmp/test_damage.jpg
"""
from __future__ import annotations

import sys
import time

import httpx

from app.core.config import settings

BASE = "http://localhost:8000/api/v1"
IMG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_damage.jpg"


def main() -> None:
    c = httpx.Client(timeout=60)
    tok = c.post(f"{BASE}/auth/login", json={
        "email": settings.seed_admin_email, "password": settings.seed_admin_password,
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    claim = c.post(f"{BASE}/claims", headers=h,
                   json={"claim_reason": "yolo verification"}).json()
    cid = claim["id"]

    slot = c.post(f"{BASE}/claims/{cid}/uploads", headers=h, json={
        "files": [{"filename": "damage.jpg", "content_type": "image/jpeg",
                   "kind": "image", "size": 0}]
    }).json()["uploads"][0]

    data = open(IMG, "rb").read()
    httpx.put(slot["upload_url"], content=data,
              headers={"Content-Type": "image/jpeg"}, timeout=60)
    c.post(f"{BASE}/claims/{cid}/uploads/{slot['asset_id']}/complete",
           headers=h, json={"sha256": None})
    c.post(f"{BASE}/claims/{cid}/submit", headers=h)

    print("Processing", end="", flush=True)
    status = None
    for _ in range(90):
        s = c.get(f"{BASE}/claims/{cid}/status", headers=h).json()
        if s["status"] in ("ready_for_review", "reviewed", "failed"):
            status = s
            break
        print(".", end="", flush=True)
        time.sleep(2)
    print()

    stages = {x["stage"]: x["status"] for x in (status or {}).get("stages", [])}
    print("pipeline status:", status["status"] if status else "timeout")
    print("detection stage:", stages.get("detection"))

    dets = c.get(f"{BASE}/claims/{cid}/detections", headers=h).json()
    defects = [d for d in dets if d["defect_label"]]
    print(f"\nTotal detections: {len(dets)} | damage detections: {len(defects)}")
    for d in defects[:10]:
        print(f"  {d['defect_label']:14} conf={d['confidence']:.2f}")

    risk = c.get(f"{BASE}/claims/{cid}/risk", headers=h).json()
    print(f"\nRisk score: {risk['score'] if risk else None}")

    ok = stages.get("detection") == "succeeded"
    print("\n" + ("\033[32mYOLO IS WIRED — detection stage ran.\033[0m" if ok
                  else "\033[31mDetection stage did not run (still skipped).\033[0m"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
