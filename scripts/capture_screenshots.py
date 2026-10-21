"""
Regenerates the screenshots in docs/images/ and the callout boxes in docs/guide/annotations.js
from a running, seeded development stack.

    python scripts/dev_backend.py                 # API on :8000 (throwaway .dev-data/ database)
    npm --prefix frontend run dev                 # app on :5173
    python scripts/seed_demo.py                   # demo data
    uv run --no-project --with playwright python scripts/capture_screenshots.py

Drives the installed Microsoft Edge (BROWSER_CHANNEL=chrome for Chrome), so Playwright doesn't
need to download a browser. Signs in with the demo credentials from .env.example -- DEV ONLY.
It also creates one MCP API key ("Claude Desktop") for the demo admin, so the keys panel isn't empty.

Each shot can name "marks": elements whose boxes are measured from the live DOM right before the
capture. They are written to docs/guide/annotations.js in screenshot pixels, and the HTML guide
draws its numbered callouts from them, so the callouts stay on target whenever the screenshots
are regenerated.
"""
import datetime
import json
import math
import os
import random
import re
import struct
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
ANNOTATIONS = ROOT / "docs" / "guide" / "annotations.js"
APP = os.environ.get("APP_URL", "http://localhost:5173")
API = os.environ.get("API_URL", "http://127.0.0.1:8000")
ADMIN_NAME = os.environ.get("DEMO_ADMIN_NAME", "demo-admin")
ADMIN_PASSWORD = os.environ.get("DEMO_ADMIN_PASSWORD", "demo-admin-pass-2026")

# name -> {"width", "height", "marks": {key: [x, y, w, h]}}; written to ANNOTATIONS at the end.
SHOTS: dict = {}
MISSING: list = []


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


def _png_size(path: Path):
    return struct.unpack(">II", path.read_bytes()[16:24])


def _box(mark, scroll):
    """Box of a locator (or the union of a list of locators), in page coordinates."""
    boxes = []
    for loc in mark if isinstance(mark, list) else [mark]:
        try:
            b = loc.bounding_box(timeout=3000)
        except PlaywrightError as e:
            print(f"    ! {str(e).splitlines()[0]}")
            b = None
        if b:
            boxes.append(b)
    if not boxes:
        return None
    x0 = min(b["x"] for b in boxes)
    y0 = min(b["y"] for b in boxes)
    x1 = max(b["x"] + b["width"] for b in boxes)
    y1 = max(b["y"] + b["height"] for b in boxes)
    return {"x": x0 + scroll[0], "y": y0 + scroll[1], "width": x1 - x0, "height": y1 - y0}


def shot(page: Page, name: str, locator=None, *, full_page=False, region=None, unclip=False, marks=None):
    """Captures docs/images/<name>.png and records where each of `marks` is in it.

    locator: shoot one element. region: shoot the union of these locators, plus a margin.
    full_page, region and unclip let the app shell grow, so nothing is cut off by its scroller.
    """
    page.wait_for_timeout(1800)  # let chart animations finish
    path = OUT / f"{name}.png"
    style = page.add_style_tag(content=UNCLIP) if (full_page or region or unclip) else None
    try:
        if style:
            page.wait_for_timeout(200)
        if locator is not None:
            locator.scroll_into_view_if_needed()
        scroll = page.evaluate("() => [window.scrollX, window.scrollY]")
        boxes = {key: _box(mark, scroll) for key, mark in (marks or {}).items()}
        if locator is not None:
            origin = _box(locator, scroll)
            locator.screenshot(path=path)
        elif region:
            area = _box(region, scroll)
            margin = 12
            x, y = max(0, math.floor(area["x"] - margin)), max(0, math.floor(area["y"] - margin))
            clip = {"x": x, "y": y,
                    "width": math.ceil(area["x"] + area["width"] + margin) - x,
                    "height": math.ceil(area["y"] + area["height"] + margin) - y}
            origin = clip
            page.screenshot(path=path, full_page=True, clip=clip)
        else:
            origin = {"x": 0, "y": 0}
            page.screenshot(path=path, full_page=full_page)
    finally:
        if style:
            style.evaluate("el => el.remove()")

    width, height = _png_size(path)
    placed = {}
    for key, b in boxes.items():
        if b is None:
            MISSING.append(f"{name}.{key}")
            continue
        # Clip to the image; a mark that ends up (almost) entirely outside it is dropped.
        x0, y0 = max(0.0, b["x"] - origin["x"]), max(0.0, b["y"] - origin["y"])
        x1 = min(width, b["x"] - origin["x"] + b["width"])
        y1 = min(height, b["y"] - origin["y"] + b["height"])
        if x1 - x0 < 2 or y1 - y0 < 2:
            MISSING.append(f"{name}.{key}")
            continue
        placed[key] = [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)]
    SHOTS[name] = {"width": width, "height": height, "marks": placed}
    print(f"  {path.relative_to(ROOT)}  ({len(placed)}/{len(boxes)} marks)")


def write_annotations():
    ANNOTATIONS.parent.mkdir(parents=True, exist_ok=True)
    rows = ",\n".join(f"  {json.dumps(name)}: {json.dumps(SHOTS[name])}" for name in sorted(SHOTS))
    ANNOTATIONS.write_text(
        "// Generated by scripts/capture_screenshots.py -- do not edit by hand.\n"
        "// Callout boxes for docs/guide/index.html, in screenshot pixels: [x, y, width, height].\n"
        f"window.GUIDE_SHOTS = {{\n{rows}\n}};\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"  {ANNOTATIONS.relative_to(ROOT)}")


def header_marks(page: Page) -> dict:
    return {
        "tabs": page.get_by_role("navigation", name="Sections"),
        "search": page.get_by_role("searchbox", name="Search KPIs"),
        "year": page.get_by_role("combobox", name="Year", exact=True),
        "facility": page.get_by_role("combobox", name="Facility", exact=True),
        "reload": page.get_by_role("button", name="Reload data"),
        "account": page.get_by_role("button", name="Log out").locator(".."),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL", "msedge"))
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        button = lambda name, scope=page: scope.get_by_role("button", name=name, exact=True)

        # --- Sign in -------------------------------------------------------------------------
        page.goto(APP)
        expect(page.get_by_text("Sign in to continue")).to_be_visible()
        page.get_by_label("Name").fill(ADMIN_NAME)
        shot(page, "login", marks={
            "brand": page.get_by_role("heading", name="KPI Target Manager"),
            "name": page.locator("#login-name"),
            "password": page.locator("#login-password"),
            "submit": page.locator("form button[type=submit]"),
        })
        page.get_by_label("Password").fill(ADMIN_PASSWORD)
        page.locator("form button[type=submit]").click()
        expect(page.get_by_text("Units Produced").first).to_be_visible()
        page.wait_for_load_state("networkidle")

        # --- Target Entry --------------------------------------------------------------------
        card = lambda kpi: page.locator("section.card", has=page.get_by_role("heading", name=kpi, exact=True))
        hours = card("Hours Worked")
        shot(page, "target-entry", marks={
            **header_marks(page),
            "context": page.locator(".glass-card", has_text="Apply saves to all visible facilities").locator("> div").first,
            "apply_all": page.locator("label", has_text="Apply saves to all visible facilities"),
            "unit": hours.locator(".badge-green"),
            "count": hours.locator(".badge-blue"),
            "split": hours.locator(".badge-purple"),
            "input": hours.get_by_role("spinbutton"),
            "history": hours.locator(".field-hint", has_text=re.compile(r"\d{4}:")).last,
            "save": button("Save", hours),
        })
        units = card("Units Produced")
        shot(page, "target-scenarios", units, marks={
            "split": units.locator(".badge-purple"),
            "count": units.locator(".badge-blue"),
            "budget": units.get_by_label("Budget"),
            "stretch": units.get_by_label("Stretch"),
            "history": units.locator(".field-hint", has_text=re.compile(r"\d{4}:")).last,
            "save": button("Save", units),
        })
        uph = card("Units per Hour")
        shot(page, "target-formula", uph, marks={
            "badge": uph.get_by_text("Formula derived"),
            "note": uph.locator("p.field-hint"),
            "input": uph.get_by_role("spinbutton"),
        })

        # --- KPI Explorer --------------------------------------------------------------------
        tab(page, "KPI Explorer")
        tree_kpi = lambda kpi: page.locator("button.tree-kpi", has_text=kpi)
        tree_kpi("Units per Hour").click()
        page.wait_for_load_state("networkidle")
        field = lambda suffix: page.locator(f"[id^='kpi-'][id$='-{suffix}']")
        section = lambda suffix: page.locator(f"section[aria-labelledby$='-{suffix}']")
        shot(page, "kpi-explorer", marks={
            "tree": page.get_by_role("list", name="KPI folders"),
            "new_folder": [page.locator("#new-folder"), page.locator("form", has=page.locator("#new-folder")).get_by_role("button")],
            "selected": tree_kpi("Units per Hour"),
            "new_kpi": [page.locator("#new-kpi"), page.locator("form", has=page.locator("#new-kpi")).get_by_role("button")],
            "save_spec": button("Save Spec"),
            "delete": button("Delete KPI"),
            "unit": [field("unit"), button("New unit")],
            "calc": field("calc"),
            "direction": field("direction"),
            "target_count": field("target-count"),
            "granularity": field("granularity"),
            "time_filter": field("time-filter"),
            "split": section("split-title"),
        })
        formula = section("formula-title")
        shot(page, "kpi-formula", formula, marks={
            "kpi_ref": page.get_by_label("Insert a KPI reference"),
            "operators": [button("Insert +"), button("Insert )")],
            "functions": [button("abs()"), button("round()")],
            "expression": field("formula"),
            "hint": field("formula-hint"),
        })

        tree_kpi("Units Produced").click()
        page.wait_for_load_state("networkidle")
        shot(page, "kpi-settings", region=[section("labels-title"), section("visibility-title")], marks={
            "names": [field("label-1"), field("label-2")],
            "thresholds": [field("warn"), field("err")],
            "formula": field("formula"),
            "plants": [section("visibility-title").locator("label").first, section("visibility-title").locator("label").last],
            "save_visibility": button("Save visibility"),
        })
        button("Audit history (show who changed what)").click()
        page.wait_for_load_state("networkidle")
        history = page.locator("section", has=button("Audit history (hide)"))
        shot(page, "kpi-history", history, marks={
            "toggle": button("Audit history (hide)"),
            "targets": history.locator("ul.history-list").first,
            "definitions": history.locator("ul.history-list").last,
        })

        # --- Global Splits & ML --------------------------------------------------------------
        tab(page, "Global Splits & ML")
        expect(page.get_by_text("Demo Seasonal (Month)").first).to_be_visible()
        row = page.locator("li.list-row", has=page.get_by_text("Demo Seasonal (Month)", exact=True))
        shot(page, "global-splits", marks={
            "name": row.locator("strong"),
            "logic": row.locator(".badge-blue"),
            "profile": row.locator(".badge-purple"),
            "years": row.locator(".badge-green"),
            "edit": row.get_by_role("button", name="Edit"),
            "delete": row.get_by_role("button", name="Delete"),
            "new_form": page.locator("#split-form-title"),
            "ml": page.locator("#ml-title"),
        })
        row.get_by_role("button", name="Edit").click()
        form = page.locator("section[aria-labelledby='split-form-title']")
        expect(page.locator("#split-name")).to_have_value("Demo Seasonal (Month)")
        shot(page, "split-editor", form, unclip=True, marks={
            "name": page.locator("#split-name"),
            "years": form.locator("fieldset", has_text="Applies to years"),
            "logic": page.locator("#split-logic"),
            "profile": page.locator("#split-profile"),
            "weights": form.locator(".weights-grid"),
            "total": form.locator("[aria-live=polite]"),
            "save": button("Save changes", form),
            "cancel": button("Cancel", form),
        })
        button("Cancel", form).click()

        dataset = Path(tmp) / "sales_history.csv"
        sample_dataset(dataset)
        page.locator("#ml-file").set_input_files(dataset)
        page.get_by_label("Date column").fill("date")
        page.get_by_label("Target column(s), comma separated").fill("units_sold")
        page.get_by_label("Driver column(s), comma separated (optional)").fill("avg_temp_c, promo_days")
        button("Race models & calculate weights").click()
        expect(page.get_by_text("Best model")).to_be_visible(timeout=120_000)
        shot(page, "ml-inputs", page.locator("section[aria-labelledby='ml-title']"), marks={
            "file": page.locator("button.upload-zone"),
            "date": page.locator("#ml-date"),
            "period": page.locator("#ml-period"),
            "targets": page.locator("#ml-targets"),
            "drivers": page.locator("#ml-features"),
            "race": button("Race models & calculate weights"),
        })
        page.mouse.move(0, 0)  # no chart tooltip in the shot
        result = page.locator("section[aria-labelledby='ml-result-title']")
        shot(page, "ml-predictor", result, marks={
            "best": page.locator("#ml-result-title"),
            "periods": result.get_by_text(re.compile(r"^Weights for \d+")),
            "publish": [page.locator("#ml-publish-name"), result.get_by_role("button", name=re.compile("^Publish as template"))],
            "chart": result.locator(".recharts-wrapper"),
            "legend": result.locator(".recharts-legend-wrapper"),
        })

        # --- Analysis & Results --------------------------------------------------------------
        tab(page, "Analysis & Results")
        expect(page.locator(".recharts-surface").first).to_be_visible()
        chart = page.locator("section[aria-labelledby='chart-title']")
        kpi_select = page.get_by_role("combobox", name="KPI", exact=True)
        granularity = page.get_by_role("combobox", name="Granularity", exact=True)
        facility_filter = page.get_by_role("combobox", name="Facility filter", exact=True)
        shot(page, "analysis", marks={
            "export": button("Export periodic targets (CSV)"),
            "kpi": kpi_select,
            "granularity": granularity,
            "facility_filter": facility_filter,
            "chart": chart.locator(".recharts-wrapper"),
            "legend": chart.locator(".recharts-legend-wrapper"),
            "table": page.locator("section[aria-labelledby='matrix-title'] table"),
        })
        kpi_select.select_option(label="Units Produced")
        granularity.select_option(label="Weekly")
        facility_filter.select_option(label="North Plant")
        page.wait_for_load_state("networkidle")
        page.mouse.move(0, 0)
        shot(page, "analysis-seasonal", chart, marks={
            "title": page.locator("#chart-title"),
            "granularity": granularity,
            "chart": chart.locator(".recharts-wrapper"),
        })

        # --- Facilities ----------------------------------------------------------------------
        tab(page, "Facilities")
        button("Edit North Plant").click()
        plant_row = page.locator("tr", has=page.get_by_role("rowheader", name="North Plant"))
        shot(page, "facilities", marks={
            "cancel": page.locator("main").get_by_role("button", name="Cancel"),
            "name": page.locator("#plant-name"),
            "description": page.locator("#plant-description"),
            "color": page.locator("#plant-color"),
            "save": button("Save facility"),
            "visibility": plant_row.locator("button[aria-pressed]"),
            "edit": button("Edit North Plant"),
            "delete": button("Delete North Plant"),
        })
        page.locator("main").get_by_role("button", name="Cancel").click()

        # --- Data Utilities ------------------------------------------------------------------
        tab(page, "Data Utilities")
        keys = page.locator("section[aria-labelledby='keys-title']")
        expect(page.get_by_role("heading", name=re.compile("^MCP API keys"))).to_be_visible()
        if keys.get_by_text("Claude Desktop", exact=True).count() == 0:
            page.locator("#new-key-label").fill("Claude Desktop")
            button("Create key", keys).click()
            expect(keys.get_by_text("copy it now", exact=False)).to_be_visible()
            page.reload()  # hides the one-time raw key
            page.wait_for_load_state("networkidle")
            tab(page, "Data Utilities")
            expect(keys.get_by_text("Claude Desktop", exact=True).first).to_be_visible()
        csv = page.locator("section[aria-labelledby='csv-title']")
        users = page.locator("section[aria-labelledby='users-title']")
        shot(page, "data-utilities", full_page=True, marks={
            "lean": button("Export lean CSV (BI-friendly)"),
            "tables": [button("Plants", csv), button("Periodic Targets", csv)],
            "backup": button("Download full backup (ZIP)"),
            "restore": [page.get_by_text("Restore from backup", exact=True), button("Choose ZIP & restore")],
            "password": page.locator("section[aria-labelledby='password-title']"),
            "users": users.locator("ul").first,
            "user_editor": page.locator(f"form[aria-label='Edit {ADMIN_NAME}']"),
            "new_user": page.locator("form[aria-labelledby='new-user-title']"),
            "keys": keys.locator("li.list-row").first,
            "new_key": [page.locator("#new-key-label"), button("Create key", keys)],
        })

        # --- Swagger UI (REST API) -----------------------------------------------------------
        docs = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        try:
            docs.goto(f"{API}/docs")
            expect(docs.locator(".swagger-ui .info .title")).to_be_visible(timeout=20_000)
            docs.wait_for_load_state("networkidle")
            shot(docs, "swagger", marks={
                "title": docs.locator(".swagger-ui .info .title"),
                "authorize": docs.locator(".swagger-ui button.authorize"),
                "tag": docs.locator("#operations-tag-auth"),
                "login": docs.locator(".opblock", has=docs.locator("[data-path='/auth/login']")),
            })
        except (PlaywrightError, AssertionError) as e:
            print(f"  ! skipped swagger.png ({str(e).splitlines()[0]})")

        browser.close()

    write_annotations()
    if MISSING:
        print("Marks not found or outside their shot:", ", ".join(MISSING))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
