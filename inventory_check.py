import os, time, logging, json
from datetime import datetime
from dateutil import tz
import requests
from playwright.sync_api import sync_playwright

# ---------- Config via env ----------
ZIP_CODES = [z.strip() for z in os.getenv("ZIP_CODES", "33172").split(",") if z.strip()]
PART_NOTES = os.getenv("PART_NOTES", "iPhone 17 Pro Max 256GB (any color)")
LOCAL_TZ   = os.getenv("LOCAL_TZ", "America/Tegucigalpa")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
SLACK_WEBHOOK      = os.getenv("SLACK_WEBHOOK", "")

BUY_PAGE = "https://www.apple.com/shop/buy-iphone/iphone-17-pro/6.9-inch-display-256gb-deep-blue-unlocked"
# ------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def notify(text: str):
    try:
        if SLACK_WEBHOOK:
            requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                params={"chat_id": TELEGRAM_CHAT_ID, "text": text},
                timeout=10
            )
    except Exception as e:
        logging.warning(f"Notify failed: {e}")

def safe_click(page, selector: str, timeout_ms: int = 3000) -> bool:
    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            return False
        loc.scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        loc.click(timeout=timeout_ms)
        return True
    except Exception:
        return False

def dismiss_overlays(page):
    for sel in [
        "button:has-text('Accept')",
        "button:has-text('Allow all')",
        "button:has-text('Allow All')",
        "button:has-text('Agree')",
        "button:has-text('Continue')",
        "[aria-label='Close']",
        "button[aria-label='Close']",
        ".ac-gn-traffic-overlay-close",
    ]:
        safe_click(page, sel, 1200)

def open_modal(page) -> bool:
    triggers = [
        "button[data-autom^='productLocatorTriggerLink_']",
        "button.rf-pickup-quote-overlay-trigger",
        "[data-autom='pickup-cta']",
        "button:has-text('Check availability')",
        "text=Check availability",
        "text=Check store availability",
    ]
    for _ in range(6):
        page.mouse.wheel(0, 1000); page.wait_for_timeout(150)
    for sel in triggers:
        try:
            page.wait_for_selector(sel, state="visible", timeout=3000)
            if safe_click(page, sel, 2500):
                return True
        except Exception:
            continue
    try:
        return page.evaluate("""
        () => {
          const sels = [
            "button[data-autom^='productLocatorTriggerLink_']",
            "button.rf-pickup-quote-overlay-trigger",
            "[data-autom='pickup-cta']"
          ];
          for (const s of sels) { const b = document.querySelector(s); if (b) { b.click(); return true; } }
          return false;
        }""")
    except Exception:
        return False

def read_results(page, zip_code: str):
    rows = []
    inputs = [
        "input[name='location']",
        "[data-autom='fulfillmentLocationInput']",
        "input[placeholder*='ZIP']",
        "input[aria-label*='ZIP']",
    ]
    field = None
    for sel in inputs:
        loc = page.locator(sel)
        if loc.count() > 0:
            field = loc.first
            break
    if field is None:
        return rows

    field.fill("")
    field.type(zip_code, delay=40)
    try: field.press("Enter")
    except Exception: pass

    page.wait_for_timeout(1700)

    containers = [
        "[data-autom='fulfillment-messages']",
        "[data-autom='fulfillment-pickup']",
        "div.rf-fulfillment-messages",
    ]
    container = None
    for sel in containers:
        loc = page.locator(sel)
        if loc.count() > 0:
            container = loc.first
            break
    if container is None:
        return rows

    store_blocks = container.locator(
        "[data-autom='store'], .rf-storelocator-store, [data-autom='fulfillment-store'], li.rf-store"
    )
    count = min(store_blocks.count(), 16)
    for i in range(count):
        sb = store_blocks.nth(i)
        try:
            name = sb.locator("[data-autom='storeName'], .rf-storelocator-name, .store-name").first.inner_text(timeout=1500)
        except Exception:
            name = "(unknown store)"

        msg = ""
        for sel in [
            "[data-autom='fulfillment-message']",
            ".rf-pickup-quote",
            ".rf-availability",
            ".as-purchaseinfo-message"
        ]:
            loc = sb.locator(sel)
            if loc.count() > 0:
                try:
                    msg = loc.first.inner_text(timeout=1000)
                    break
                except Exception:
                    pass

        rows.append({
            "zip": zip_code,
            "store": name,
            "available": "available" in (msg or "").lower(),
            "message": (msg or "").strip(),
        })
    return rows

def run_once() -> dict:
    tzinfo = tz.gettz(LOCAL_TZ)
    out = {
        "timestamp": datetime.now(tzinfo).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "part_notes": PART_NOTES,
        "zips": ZIP_CODES,
        "rows": [],
        "errors": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="en-US")
        page = ctx.new_page()

        page.goto(BUY_PAGE, wait_until="domcontentloaded")
        dismiss_overlays(page)
        if not open_modal(page):
            out["errors"].append("Could not open availability modal")
            try: os.makedirs("docs/data", exist_ok=True); page.screenshot(path="docs/data/page_no_modal.png", full_page=True)
            except Exception: pass
            ctx.close(); browser.close()
            return out

        for z in ZIP_CODES:
            try:
                rows = read_results(page, z)
                out["rows"].extend(rows)
                hits = [r for r in rows if r["available"]]
                if hits:
                    text = f"📱 Pickup available [{z}] — " + \"; \".join(f\"{h['store']} ({h['message']})\" for h in hits)
                    logging.info(text)
                    notify(text)
            except Exception as e:
                out["errors"].append(f\"{z}: {e}\")

        ctx.close(); browser.close()

    return out

if __name__ == "__main__":
    data = run_once()
    os.makedirs("docs/data", exist_ok=True)
    with open("docs/data/latest.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open("docs/data/last.txt", "w", encoding="utf-8") as f:
        if data["rows"]:
            yes = sum(1 for r in data["rows"] if r["available"])
            f.write(f"{data['timestamp']} — {yes} available out of {len(data['rows'])} stores\n")
        else:
            f.write(f"{data['timestamp']} — no rows (modal might have failed)\n")
    print(json.dumps(data, ensure_ascii=False))
