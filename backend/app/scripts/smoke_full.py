"""Full end-to-end smoke test through the LIVE HTTP API — proves every subsystem
is wired into the running app: claim -> upload -> pipeline -> serial checks ->
battery report -> telemetry -> unified verdict -> report.

Run inside the api container:
    docker compose exec -T api python -m app.scripts.smoke_full
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
ABUSE_VIN = "1HGBH41JXMN109186"   # seeded telemetry profile = abuse
_n = 0


def step(ok: bool, label: str, detail: str = "") -> None:
    global _n
    _n += 1
    print(f"  [{_n:02d}] {PASS if ok else FAIL}  {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        print("\nSMOKE FAILED.")
        sys.exit(1)


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (120, 120, 120)).save(buf, format="JPEG")
    return buf.getvalue()


def main() -> None:
    print("WarrantyLens full wiring smoke test\n")
    c = httpx.Client(timeout=60)

    tok = c.post(f"{BASE}/auth/login", json={
        "email": settings.seed_admin_email, "password": settings.seed_admin_password,
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    step(True, "Login")

    # Claim on abuse VIN, with a serial that belongs to ANOTHER vehicle (integrity flag).
    cid = c.post(f"{BASE}/claims", headers=h, json={
        "vin": ABUSE_VIN, "claim_reason": "charging port + battery fault",
        "removed_serial": "CP-5YJ-3310", "replacement_serial": "CP-NEW-0001",
    }).json()["id"]
    step(True, "Create claim (with serials)")

    slot = c.post(f"{BASE}/claims/{cid}/uploads", headers=h, json={
        "files": [{"filename": "d.jpg", "content_type": "image/jpeg", "kind": "image", "size": 0}],
    }).json()["uploads"][0]
    httpx.put(slot["upload_url"], content=_jpeg(), headers={"Content-Type": "image/jpeg"}, timeout=60)
    c.post(f"{BASE}/claims/{cid}/uploads/{slot['asset_id']}/complete", headers=h, json={"sha256": None})
    step(True, "Upload evidence")

    c.post(f"{BASE}/claims/{cid}/submit", headers=h)
    final = None
    for _ in range(120):
        s = c.get(f"{BASE}/claims/{cid}/status", headers=h).json()
        if s["status"] in ("ready_for_review", "failed"):
            final = s
            break
        time.sleep(3)
    step(final is not None and final["status"] == "ready_for_review",
         "Pipeline complete", final["status"] if final else "timeout")

    # Telemetry wired (abuse VIN -> suggests_misuse).
    tel = c.get(f"{BASE}/vehicles/{ABUSE_VIN}/telemetry", headers=h).json()
    step(tel.get("summary", {}).get("days", 0) > 0, "Telemetry present", f"leaning={tel.get('leaning')}")

    # Serial integrity factor present in risk.
    risk = c.get(f"{BASE}/claims/{cid}/risk", headers=h).json()
    srcs = {f["source"] for f in (risk or {}).get("factors", [])}
    step("serial" in srcs, "Serial integrity factor in risk", f"sources={sorted(srcs)}")
    step("telemetry" in srcs, "Telemetry factor in risk")

    # Attach battery report (abuse) -> recomputes.
    bhr = {"source": "BatteryOS", "soh_percent": 78, "vehicle": {"vin": ABUSE_VIN},
           "abuse_indicators": ["frequent_hot_fast_charge", "deep_discharge"],
           "faults": [{"code": "P0A80", "severity": "high"}], "rul": {"cycles": 600}}
    br = c.post(f"{BASE}/claims/{cid}/battery-report", headers=h, json=bhr).json()
    step(br.get("warranty_leaning") == "suggests_misuse", "Battery report attached",
         f"leaning={br.get('warranty_leaning')}")

    # Unified verdict reflects everything.
    v = c.get(f"{BASE}/claims/{cid}/verdict", headers=h).json()
    vsrc = {s["source"] for s in v.get("sources", [])}
    step(v["verdict"] == "likely_misuse_or_external", "Unified verdict", v["verdict"])
    step(v["integrity_concern"] is True, "Verdict flags serial integrity concern")
    step({"battery", "telemetry"}.issubset(vsrc), "Verdict fuses multiple sources", f"sources={sorted(vsrc)}")

    # Report includes the verdict.
    rep = c.get(f"{BASE}/claims/{cid}/report", headers=h).json()
    step(rep and rep.get("payload", {}).get("verdict"), "Report embeds verdict")

    print(f"\n\033[32mALL {_n} CHECKS PASSED — every subsystem is wired into the running app.\033[0m")


if __name__ == "__main__":
    main()
