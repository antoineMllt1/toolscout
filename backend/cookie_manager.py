"""
Automatic CF cookie harvester + persistent store.

Strategy:
  - On startup: load cookies from DB, fall back to hardcoded defaults
  - Every REFRESH_INTERVAL seconds: open a fresh Playwright session per source,
    let it resolve the CF challenge natively, extract & persist the new cookies
  - Scrapers always read from the in-memory COOKIES dict (kept fresh by this module)

Sources requiring CF cookies:
  - indeed:    https://fr.indeed.com
  - jobteaser: https://www.jobteaser.com/fr/job-offers
"""
import asyncio
import json
import time
import logging
from datetime import datetime, timedelta

import aiosqlite

from database import DB_PATH

log = logging.getLogger("cookie_manager")

REFRESH_INTERVAL = 6 * 3600   # re-harvest every 6 hours
COOKIE_TTL_HOURS = 12          # warn if cookies are older than this

HARVEST_TARGETS = {
    "indeed": {
        "url":    "https://fr.indeed.com/emplois?q=test",
        "domain": ".indeed.com",
        "wait":   "networkidle",
        "extra_wait": 3000,
    },
    "jobteaser": {
        "url":    "https://www.jobteaser.com/fr/job-offers?query=test",
        "domain": ".jobteaser.com",
        "wait":   "networkidle",
        "extra_wait": 3000,
    },
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# In-memory cookie store (shared with main.py via reference)
# Populated by load_cookies_from_db() and updated by harvest tasks
_store: dict[str, dict] = {}


# ── DB helpers ────────────────────────────────────────────────────────────────

async def ensure_cookies_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cf_cookies (
                source      TEXT PRIMARY KEY,
                cookies_json TEXT NOT NULL,
                harvested_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def load_cookies_from_db() -> dict[str, dict]:
    """Load all stored cookies into memory. Returns {source: {name: value}}."""
    await ensure_cookies_table()
    result = {}
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT source, cookies_json, harvested_at FROM cf_cookies")
        rows = await cur.fetchall()
    for row in rows:
        try:
            age_hours = (datetime.utcnow() - datetime.fromisoformat(row["harvested_at"])).total_seconds() / 3600
            cookies = json.loads(row["cookies_json"])
            result[row["source"]] = cookies
            if age_hours > COOKIE_TTL_HOURS:
                log.warning(f"[cookies] {row['source']} cookies are {age_hours:.0f}h old — will refresh")
            else:
                log.info(f"[cookies] Loaded {row['source']} cookies ({age_hours:.1f}h old)")
        except Exception as e:
            log.error(f"[cookies] Failed to load {row['source']}: {e}")
    return result


async def save_cookies_to_db(source: str, cookies: dict):
    await ensure_cookies_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO cf_cookies (source, cookies_json, harvested_at)
               VALUES (?, ?, ?)
               ON CONFLICT(source) DO UPDATE SET
                 cookies_json = excluded.cookies_json,
                 harvested_at = excluded.harvested_at""",
            (source, json.dumps(cookies), datetime.utcnow().isoformat()),
        )
        await db.commit()
    log.info(f"[cookies] Saved {source} cookies to DB ({list(cookies.keys())})")


# ── Playwright harvester ──────────────────────────────────────────────────────

def _harvest_sync(source: str) -> dict:
    """
    Synchronous Playwright session that visits the target URL,
    waits for CF to resolve, and returns extracted cookies.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("[cookies] Playwright not installed")
        return {}

    target = HARVEST_TARGETS.get(source)
    if not target:
        return {}

    log.info(f"[cookies] Harvesting {source} cookies via Playwright…")
    cookies = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            ctx = browser.new_context(
                user_agent=UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1280, "height": 900},
                # Mask automation signals
                extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
            )

            # Remove navigator.webdriver flag
            ctx.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            page = ctx.new_page()
            try:
                page.goto(target["url"], wait_until=target["wait"], timeout=40000)
            except Exception:
                pass  # networkidle might timeout on CF pages — that's ok

            page.wait_for_timeout(target["extra_wait"])

            # Extract all cookies for this domain
            all_cookies = ctx.cookies()
            domain = target["domain"]
            for c in all_cookies:
                if domain in (c.get("domain") or ""):
                    cookies[c["name"]] = c["value"]

            browser.close()
    except Exception as e:
        log.error(f"[cookies] Harvest failed for {source}: {e}")

    if cookies:
        log.info(f"[cookies] ✓ Harvested {source}: {list(cookies.keys())}")
    else:
        log.warning(f"[cookies] ✗ No cookies harvested for {source}")

    return cookies


async def harvest_source(source: str, live_store: dict) -> bool:
    """Harvest cookies for one source and update the live store."""
    loop = asyncio.get_event_loop()
    cookies = await loop.run_in_executor(None, lambda: _harvest_sync(source))
    if cookies:
        live_store[source] = cookies
        await save_cookies_to_db(source, cookies)
        return True
    return False


# ── Background refresh loop ───────────────────────────────────────────────────

async def cookie_refresh_loop(live_store: dict):
    """
    Background task. Runs forever:
      - Immediately harvest on startup if cookies are missing or stale
      - Then refresh every REFRESH_INTERVAL seconds
    """
    # Initial pass: harvest any missing sources immediately
    for source in HARVEST_TARGETS:
        if source not in live_store:
            log.info(f"[cookies] {source} not in store — harvesting now")
            await harvest_source(source, live_store)
        else:
            log.info(f"[cookies] {source} already in store — skipping initial harvest")

    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        log.info("[cookies] Starting scheduled cookie refresh…")
        for source in HARVEST_TARGETS:
            await harvest_source(source, live_store)
            await asyncio.sleep(5)  # small gap between sources
