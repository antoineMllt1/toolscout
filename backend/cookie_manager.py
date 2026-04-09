"""
Automatic Cloudflare cookie harvester and persistent store.

Strategy:
  - On startup: load cookies from DB.
  - Every REFRESH_INTERVAL seconds: open a fresh Playwright session per source,
    let it resolve the challenge, extract cookies, and persist them.
  - Scrapers always read from the in-memory COOKIES dict shared with main.py.
"""
import asyncio
import json
import logging
from datetime import datetime

import aiosqlite

from database import DB_PATH

log = logging.getLogger("toolscout.cookies")

REFRESH_INTERVAL = 6 * 3600
COOKIE_TTL_HOURS = 12

HARVEST_TARGETS = {
    "indeed": {
        "url": "https://fr.indeed.com/emplois?q=test",
        "domain": ".indeed.com",
        "wait": "networkidle",
        "extra_wait": 3000,
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
            age_hours = (
                datetime.utcnow() - datetime.fromisoformat(row["harvested_at"])
            ).total_seconds() / 3600
            cookies = json.loads(row["cookies_json"])
            result[row["source"]] = cookies
            if age_hours > COOKIE_TTL_HOURS:
                log.warning("%s cookies are %.0fh old; refresh recommended", row["source"], age_hours)
            else:
                log.info("Loaded %s cookies (%.1fh old)", row["source"], age_hours)
        except Exception as e:
            log.error("Failed to load %s cookies: %s", row["source"], e)

    return result


async def save_cookies_to_db(source: str, cookies: dict):
    await ensure_cookies_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO cf_cookies (source, cookies_json, harvested_at)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                cookies_json = excluded.cookies_json,
                harvested_at = excluded.harvested_at
            """,
            (source, json.dumps(cookies), datetime.utcnow().isoformat()),
        )
        await db.commit()

    log.info("Saved %s cookies to DB keys=%s", source, list(cookies.keys()))


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
                """
            )

            page = ctx.new_page()
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
        log.warning("No cookies harvested for %s", source)

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
    for source in HARVEST_TARGETS:
        if source not in live_store:
            log.info("%s not in store; harvesting now", source)
            await harvest_source(source, live_store)
        else:
            log.info("%s already in store; skipping initial harvest", source)

    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        log.info("Starting scheduled cookie refresh")
        for source in HARVEST_TARGETS:
            await harvest_source(source, live_store)
            await asyncio.sleep(5)
