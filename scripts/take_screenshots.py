"""
Capture LinkedIn-ready screenshots of the WarrantyLens app.
Run from project root: python scripts/take_screenshots.py
"""
import time, json, os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
API  = "http://localhost:8000/api/v1"
OUT  = os.path.join(os.path.dirname(__file__), "../linkedin_assets")
os.makedirs(OUT, exist_ok=True)

CREDS = {"email": "admin@demo.warrantylens.io", "password": "Admin12345!"}

PAGES = [
    ("01_login",         "/login",      "Login — WarrantyLens"),
    ("02_dashboard",     "/dashboard",  "Dashboard"),
    ("03_claims_list",   "/claims",     "Claims"),
    ("04_vehicles",      "/vehicles",   "Vehicles (Digital Passport)"),
]

def login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[type='email']", CREDS["email"])
    page.fill("input[type='password']", CREDS["password"])
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard", timeout=15000)
    time.sleep(1)

def shot(page, name, path, viewport={"width": 1440, "height": 900}):
    page.set_viewport_size(viewport)
    page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=20000)
    time.sleep(1.5)
    out = os.path.join(OUT, f"{name}.png")
    page.screenshot(path=out, full_page=False)
    print(f"  ✓ {name}.png")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # Login first
    print("Logging in...")
    login(page)
    print("Logged in.")

    # Dashboard
    shot(page, "02_dashboard", "/dashboard")

    # Claims list
    shot(page, "03_claims_list", "/claims")

    # Vehicles
    shot(page, "04_vehicles", "/vehicles")

    # Try to get first claim id and screenshot claim detail
    import urllib.request, urllib.error
    time.sleep(3)  # avoid rate-limit
    token_resp = urllib.request.urlopen(
        urllib.request.Request(
            f"{API}/auth/login",
            data=json.dumps(CREDS).encode(),
            headers={"Content-Type": "application/json"},
        )
    )
    token = json.loads(token_resp.read())["access_token"]

    claims_resp = urllib.request.urlopen(
        urllib.request.Request(
            f"{API}/claims?limit=20",
            headers={"Authorization": f"Bearer {token}"},
        )
    )
    claims_data = json.loads(claims_resp.read())
    items = claims_data.get("items", claims_data) if isinstance(claims_data, dict) else claims_data
    if items:
        # Prefer a ready_for_review claim for richer detail
        best = next((c for c in items if c.get("status") == "ready_for_review"), items[0])
        cid = best["id"]
        shot(page, "05_claim_detail", f"/claims/{cid}")
        vin = best.get("vin", "")
        if vin:
            shot(page, "06_vehicle_passport", f"/vehicles/{vin}")

    # API docs
    page.goto("http://localhost:8000/docs", wait_until="networkidle", timeout=15000)
    time.sleep(2)
    page.screenshot(path=os.path.join(OUT, "07_api_docs.png"), full_page=False)
    print("  ✓ 07_api_docs.png")

    # Login page (last, after all logged-in shots)
    page.goto(f"{BASE}/login", wait_until="networkidle")
    time.sleep(1)
    page.screenshot(path=os.path.join(OUT, "01_login.png"), full_page=False)
    print("  ✓ 01_login.png")

    browser.close()

print(f"\nAll screenshots saved to: {OUT}")
