"""Push a real image through the FULL AI pipeline and report every stage.
Run in the api container:
    docker compose exec -T api python -m app.scripts.verify_pipeline /tmp/test_damage.jpg
Patient (up to ~30 min) because first run downloads BGE-M3 + Paddle weights.
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

    cid = c.post(f"{BASE}/claims", headers=h,
                 json={"claim_reason": "full pipeline test", "vin": "1HGBH41JXMN109186"}).json()["id"]
    slot = c.post(f"{BASE}/claims/{cid}/uploads", headers=h, json={
        "files": [{"filename": "damage.jpg", "content_type": "image/jpeg", "kind": "image", "size": 0}]
    }).json()["uploads"][0]
    httpx.put(slot["upload_url"], content=open(IMG, "rb").read(),
              headers={"Content-Type": "image/jpeg"}, timeout=60)
    c.post(f"{BASE}/claims/{cid}/uploads/{slot['asset_id']}/complete", headers=h, json={"sha256": None})
    c.post(f"{BASE}/claims/{cid}/submit", headers=h)
    print(f"claim {cid} submitted; processing (first run downloads models, be patient)…\n")

    seen = {}
    final = None
    for _ in range(600):  # ~30 min
        s = c.get(f"{BASE}/claims/{cid}/status", headers=h).json()
        for st in s.get("stages", []):
            if seen.get(st["stage"]) != st["status"]:
                seen[st["stage"]] = st["status"]
                print(f"  stage {st['stage']:16} -> {st['status']}")
        if s["status"] in ("ready_for_review", "reviewed", "failed"):
            final = s
            break
        time.sleep(3)

    print(f"\nfinal status: {final['status'] if final else 'timeout'}")
    if final and final.get("processing_error"):
        print("error:", final["processing_error"])

    det = c.get(f"{BASE}/claims/{cid}/detections", headers=h).json()
    ocr = c.get(f"{BASE}/claims/{cid}/ocr", headers=h).json()
    vlm = c.get(f"{BASE}/claims/{cid}/vlm", headers=h).json()
    risk = c.get(f"{BASE}/claims/{cid}/risk", headers=h).json()

    print(f"\nDETECTIONS ({len([d for d in det if d['defect_label']])} damage):")
    for d in det:
        if d["defect_label"]:
            print(f"   {d['defect_label']:14} {d['confidence']:.2f}")
    print(f"\nOCR ({len(ocr)}):")
    for o in ocr:
        if o["field_type"] in ("vin", "serial"):
            print(f"   {o['field_type']}: {o['normalized_value']}")
    print(f"\nVLM ({len(vlm)} keyframes):")
    for v in vlm[:3]:
        print(f"   {v['model_version']}: {(v['description'] or '')[:140]}")
    print(f"\nRISK: {risk['score'] if risk else None}  |  {risk['rationale'][:160] if risk else ''}")


if __name__ == "__main__":
    main()
