"""
Regenerates the screenshots in docs/images/ from a running, seeded development stack.

    python scripts/dev_backend.py                 # API on :8000 (throwaway .dev-data/ database)
    npm --prefix frontend run dev                 # app on :5173
    python scripts/seed_demo.py                   # demo data
    uv run --no-project --with playwright python scripts/capture_screenshots.py

Drives the installed Microsoft Edge (BROWSER_CHANNEL=chrome for Chrome), so Playwright doesn't
need to download a browser. Signs in with the demo credentials from .env.example -- DEV ONLY.
"""
import datetime
import math
import os
import random
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
APP = os.environ.get("APP_URL", "http://localhost:5173")
ADMIN_NAME = os.environ.get("DEMO_ADMIN_NAME", "demo-admin")
ADMIN_PASSWORD = os.environ.get("DEMO_ADMIN_PASSWORD", "demo-admin-pass-2026")


def sample_dataset(path: Path):
    """Two years of daily sales with a winter peak, driven by temperature and promotions."""
    rng = random.Random(7)
    rows = ["date,units_sold,avg_temp_c,promo_days"]
    start = datetime.date(datetime.date.today().year - 2, 1, 1)
    for i in range(730):
        day = start + datetime.timedelta(days=i)
        temp = 12 - 10 * math.cos(2 * math.pi * (day.timetuple().tm_yday - 15) / 365) + rng.gauss(0, 2)
        promo = 1 if day.month in (11, 12) and rng.random() < 0.4 else 0
        units = 300 - 6 * temp + 120 * promo + rng.gauss(0, 15)
        rows.append(f"{day.isoformat()},{units:.0f},{temp:.1f},{promo}")
    path.write_text("\n".join(rows), encoding="utf-8")


def tab(page: Page, name: str):
    page.get_by_role("button", name=name, exact=True).click()
    page.wait_for_load_state("networkidle")


# The app scrolls inside <main> (the shell is 100vh); for a full-page shot let it grow instead.
UNCLIP = ".app-container, .main-workspace, .workspace-content { height: auto !important; overflow: visible !important; }"


def shot(page: Page, name: str, locator=None, full_page: bool = False):
    page.wait_for_timeout(1800)  # let chart animations finish
    path = OUT / f"{name}.png"
    if locator is not None:
        locator.screenshot(path=path)
    elif full_page:
        style = page.add_style_tag(content=UNCLIP)
        page.screenshot(path=path, full_page=True)
        style.evaluate("el => el.remove()")
    else:
        page.screenshot(path=path)
    print(f"  {path.relative_to(ROOT)}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL", "msedge"))
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        page.goto(APP)

        expect(page.get_by_text("Sign in to continue")).to_be_visible()
        page.get_by_label("Name").fill(ADMIN_NAME)
        shot(page, "login")
        page.get_by_label("Password").fill(ADMIN_PASSWORD)
        page.get_by_role("button", name="Sign In", exact=True).click()
        expect(page.get_by_text("Units Produced").first).to_be_visible()
        page.wait_for_load_state("networkidle")
        shot(page, "target-entry")

        tab(page, "KPI Explorer")
        page.get_by_role("button", name="Units per Hour").click()
        page.wait_for_load_state("networkidle")
        shot(page, "kpi-explorer")
        formula = page.locator("section", has=page.get_by_role("heading", name="Formula"))
        shot(page, "kpi-formula", formula)
        page.get_by_role("button", name="Units Produced").click()
        page.get_by_role("button", name="Audit history (show who changed what)").click()
        page.wait_for_load_state("networkidle")
        history = page.locator("section", has=page.get_by_role("button", name="Audit history (hide)"))
        shot(page, "kpi-history", history)

        tab(page, "Global Splits & ML")
        expect(page.get_by_text("Demo Seasonal (Month)").first).to_be_visible()
        shot(page, "global-splits")
        dataset = Path(tmp) / "sales_history.csv"
        sample_dataset(dataset)
        page.locator("#ml-file").set_input_files(dataset)
        page.get_by_label("Date column").fill("date")
        page.get_by_label("Target column(s), comma separated").fill("units_sold")
        page.get_by_label("Driver column(s), comma separated (optional)").fill("avg_temp_c, promo_days")
        page.get_by_role("button", name="Race models & calculate weights").click()
        expect(page.get_by_text("Best model")).to_be_visible(timeout=120_000)
        shot(page, "ml-inputs", page.locator("section[aria-labelledby='ml-title']"))
        page.mouse.move(0, 0)  # no chart tooltip in the shot
        shot(page, "ml-predictor", page.locator("section[aria-labelledby='ml-result-title']"))

        tab(page, "Analysis & Results")
        expect(page.locator(".recharts-surface").first).to_be_visible()
        shot(page, "analysis")

        tab(page, "Facilities")
        shot(page, "facilities")

        tab(page, "Data Utilities")
        expect(page.get_by_role("heading", name="MCP API keys")).to_be_visible()
        shot(page, "data-utilities", full_page=True)
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
