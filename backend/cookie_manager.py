"""
Automatic Cloudflare cookie harvester and persistent store.

Strategy:
  - On startup: load cookies from DB.
  - If any source has stale (> COOKIE_TTL_HOURS) or missing cookies, harvest immediately.
  - Every REFRESH_INTERVAL seconds: refresh all sources.
  - Scrapers always read from the in-memory COOKIES dict shared with main.py.
"""
import asyncio
import json
import logging
from datetime import datetime

import aiosqlite

from database import DB_PATH

log = logging.getLogger("toolscout.cookies")

REFRESH_INTERVAL = 2 * 3600   # re-harvest every 2 hours
COOKIE_TTL_HOURS = 10          # warn + re-harvest immediately if older than this

HARVEST_TARGETS = {
    "indeed": {
        "url": "https://fr.indeed.com/emplois?q=test",
        "domain": ".indeed.com",
        "wait": "networkidle",
        "extra_wait": 4000,
    },
    "jobteaser": {
        "url": "https://www.jobteaser.com/fr/job-offers?query=test",
        "domain": ".jobteaser.com",
        "wait": "networkidle",
        "extra_wait": 3000,
    },
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# In-memory mapping: source -> harvested_at (datetime)
_cookie_ages: dict[str, datetime] = {}


async def ensure_cookies_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS cf_cookies (
                source TEXT PRIMARY KEY,
                cookies_json TEXT NOT NULL,
                harvested_at TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def load_cookies_from_db() -> dict[str, dict]:
    await ensure_cookies_table()
    result = {}

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT source, cookies_json, harvested_at FROM cf_cookies")
        rows = await cur.fetchall()

    for row in rows:
        try:
            harvested_at = datetime.fromisoformat(row["harvested_at"])
            age_hours = (datetime.utcnow() - harvested_at).total_seconds() / 3600
            cookies = json.loads(row["cookies_json"])
            result[row["source"]] = cookies
            _cookie_ages[row["source"]] = harvested_at
            if age_hours > COOKIE_TTL_HOURS:
                log.warning(
                    "%s cookies are %.0fh old (threshold %sh) — will re-harvest now",
                    row["source"], age_hours, COOKIE_TTL_HOURS,
                )
            else:
                log.info("Loaded %s cookies (%.1fh old)", row["source"], age_hours)
        except Exception as e:
            log.error("Failed to load %s cookies: %s", row["source"], e)

    return result


async def save_cookies_to_db(source: str, cookies: dict):
    await ensure_cookies_table()
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO cf_cookies (source, cookies_json, harvested_at)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                cookies_json = excluded.cookies_json,
                harvested_at = excluded.harvested_at
            """,
            (source, json.dumps(cookies), now.isoformat()),
        )
        await db.commit()
    _cookie_ages[source] = now
    log.info("Saved %s cookies to DB keys=%s", source, list(cookies.keys()))


def _cookie_age_hours(source: str) -> float:
    if source not in _cookie_ages:
        return float("inf")
    return (datetime.utcnow() - _cookie_ages[source]).total_seconds() / 3600


def _harvest_sync(source: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright not installed")
        return {}

    target = HARVEST_TARGETS.get(source)
    if not target:
        return {}

    log.info("Harvesting %s cookies via Playwright", source)
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
                extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
            )

            ctx.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                """
            )

            page = ctx.new_page()
            # block heavy resources to speed up harvest
            page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )

            try:
                page.goto(target["url"], wait_until=target["wait"], timeout=40000)
            except Exception:
                pass

            page.wait_for_timeout(target["extra_wait"])

            for cookie in ctx.cookies():
                if target["domain"] in (cookie.get("domain") or ""):
                    cookies[cookie["name"]] = cookie["value"]

            browser.close()
    except Exception as e:
        log.error("Harvest failed for %s: %s", source, e)

    if cookies:
        log.info("Harvested %s cookies keys=%s", source, list(cookies.keys()))
    else:
        log.warning("No cookies harvested for %s — site may still be blocking headless", source)

    return cookies


async def harvest_source(source: str, live_store: dict) -> bool:
    loop = asyncio.get_event_loop()
    cookies = await loop.run_in_executor(None, lambda: _harvest_sync(source))
    if cookies:
        live_store[source] = cookies
        await save_cookies_to_db(source, cookies)
        return True
    return False


async def cookie_refresh_loop(live_store: dict):
    """
    On startup: harvest any source that is missing OR whose cookies are older than COOKIE_TTL_HOURS.
    Then re-harvest all sources every REFRESH_INTERVAL seconds.
    """
    for source in HARVEST_TARGETS:
        age = _cookie_age_hours(source)
        if source not in live_store or age > COOKIE_TTL_HOURS:
            reason = "missing" if source not in live_store else f"{age:.0f}h old (stale)"
            log.info("%s cookies %s — harvesting now", source, reason)
            await harvest_source(source, live_store)
            await asyncio.sleep(5)
        else:
            log.info("%s cookies are fresh (%.1fh old) — skipping initial harvest", source, age)

    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        log.info("Starting scheduled cookie refresh (every %dh)", REFRESH_INTERVAL // 3600)
        for source in HARVEST_TARGETS:
            await harvest_source(source, live_store)
            await asyncio.sleep(5)
