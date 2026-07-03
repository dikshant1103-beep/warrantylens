"""
Additional screenshots: vehicle passport, dark mode dashboard, claim detail scrolled.
"""
import time, json, os, urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
API  = "http://localhost:8000/api/v1"
OUT  = os.path.join(os.path.dirname(__file__), "../linkedin_assets")
CREDS = {"email": "admin@demo.warrantylens.io", "password": "Admin12345!"}

def login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[type='email']", CREDS["email"])
    page.fill("input[type='password']", CREDS["password"])
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard", timeout=15000)
    time.sleep(1.5)

def shot(page, name, url=None, scroll_y=0, extra_wait=1.5):
    if url:
        page.goto(url, wait_until="networkidle", timeout=25000)
    time.sleep(extra_wait)
    if scroll_y:
        page.evaluate(f"window.scrollTo(0, {scroll_y})")
        time.sleep(0.8)
    out = os.path.join(OUT, f"{name}.png")
    page.screenshot(path=out, full_page=False)
    print(f"  ✓ {name}.png")

# Get claim + vin from API
time.sleep(2)
tok = json.loads(urllib.request.urlopen(
    urllib.request.Request(f"{API}/auth/login",
        data=json.dumps(CREDS).encode(),
        headers={"Content-Type": "application/json"})
).read())["access_token"]

claims_data = json.loads(urllib.request.urlopen(
    urllib.request.Request(f"{API}/claims?limit=20",
        headers={"Authorization": f"Bearer {tok}"})
).read())
items = claims_data.get("items", [])
best = next((c for c in items if c.get("status") == "ready_for_review"), items[0] if items else None)
cid  = best["id"] if best else None
vin  = best.get("vin", "1HGBH41JXMN109186") if best else "1HGBH41JXMN109186"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])

    # — Light mode: vehicle passport —
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    login(page)
    shot(page, "06_vehicle_passport", f"{BASE}/vehicles/{vin}")
    # scroll down on passport to show telemetry/parts
    shot(page, "06b_passport_telemetry", scroll_y=500)
    ctx.close()

    # — Dark mode: dashboard —
    ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
    page2 = ctx2.new_page()
    login(page2)
    # Toggle dark mode via the moon button (or localStorage)
    page2.evaluate("localStorage.setItem('wl-theme','dark'); document.documentElement.classList.add('dark')")
    page2.reload(wait_until="networkidle")
    time.sleep(1.5)
    shot(page2, "08_dashboard_dark")

    # Dark mode: claim detail
    if cid:
        shot(page2, "09_claim_detail_dark", f"{BASE}/claims/{cid}")
        # scroll to risk factors table
        shot(page2, "09b_claim_risk_factors_dark", scroll_y=500)

    ctx2.close()

    # — Claim detail scrolled (light) to show parts & battery panel —
    ctx3 = browser.new_context(viewport={"width": 1440, "height": 900})
    page3 = ctx3.new_page()
    login(page3)
    if cid:
        page3.goto(f"{BASE}/claims/{cid}", wait_until="networkidle", timeout=25000)
        time.sleep(2)
        # scroll to bottom panels
        shot(page3, "10_claim_parts_battery", scroll_y=1200)
    ctx3.close()

    browser.close()

print(f"\nDone. Assets at: {OUT}")
