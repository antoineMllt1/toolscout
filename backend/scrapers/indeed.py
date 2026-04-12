"""
Indeed France scraper.

Uses Playwright with a small stealth layer to pass Cloudflare and then reads the
job description from the side panel or the viewjob page.
"""
import time
from typing import Iterator

from .base import BaseScraper, JobResult, parse_html

SEARCH_URL = "https://fr.indeed.com/emplois"
VIEWJOB_URL = "https://fr.indeed.com/viewjob?jk={jk}"

INDEED_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class IndeedScraper(BaseScraper):
    SOURCE = "indeed"
    DELAY = 0.35
    MAX_PAGES = 1
    MAX_SCANNED_CARDS = 4
    MAX_DURATION = 15
    SEARCH_TIMEOUT_MS = 12000
    DETAIL_TIMEOUT_MS = 7000

    _CARD_SELECTORS = "div[data-jk], div.job_seen_beacon"
    _DESC_SEL = (
        "#jobDescriptionText, "
        ".jobsearch-jobDescriptionText, "
        "[data-testid='jobsearch-JobComponent-description'], "
        ".job-description, "
        "#job-details-content, "
        "[id*='jobDescriptionText'], "
        ".jobDescriptionContent"
    )

    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        self._cookies_dict = cookies or {}

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        yield from self._search_playwright(tool, max_results)

    def _search_playwright(self, tool: str, max_results: int) -> Iterator[JobResult]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.log.error("Playwright not installed")
            return

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
                user_agent=INDEED_UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8"},
            )
            self._apply_stealth(ctx)
            self._inject_cookies(ctx)

            page = ctx.new_page()
            self._apply_resource_blocking(page)
            detail_ctx = browser.new_context(
                user_agent=INDEED_UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8"},
            )
            self._apply_stealth(detail_ctx)
            self._inject_cookies(detail_ctx)
            detail_page = detail_ctx.new_page()
            self._apply_resource_blocking(detail_page)
            count = 0
            start = 0
            seen_jk: set[str] = set()
            started_at = time.monotonic()

            while count < max_results:
                if time.monotonic() - started_at > self.MAX_DURATION:
                    self.log.warning("Indeed time budget reached after %.1fs", time.monotonic() - started_at)
                    break
                url = f"{SEARCH_URL}?q={tool}&l=France&sort=date&start={start}"
                if not self._load_results_page(page, url):
                    break

                html = page.content()
                cards = self._parse_cards(html)
                self.log.info("Indeed page start=%s cards=%s", start, len(cards))
                if not cards:
                    break

                for idx, card in enumerate(cards):
                    if count >= max_results:
                        break
                    if idx >= self.MAX_SCANNED_CARDS:
                        break
                    if time.monotonic() - started_at > self.MAX_DURATION:
                        break

                    jk = card.get("jk", "")
                    if not jk or jk in seen_jk:
                        continue
                    seen_jk.add(jk)

                    snippet_context = self.extract_tool_context(card.get("snippet", ""), tool)
                    if snippet_context:
                        yield JobResult(
                            company_name=card.get("company", ""),
                            job_title=card.get("title", ""),
                            job_url=card.get("url") or f"https://fr.indeed.com/viewjob?jk={jk}",
                            location=card.get("location", ""),
                            contract_type=card.get("contract", ""),
                            tool_context=snippet_context,
                            source=self.SOURCE,
                        )
                        count += 1
                        continue

                    description = self._get_description_via_search_page(
                        detail_page=detail_page,
                        tool=tool,
                        start=start,
                        jk=jk,
                    )
                    time.sleep(self.DELAY)
                    if not description:
                        continue

                    context = self.extract_tool_context(description, tool)
                    if not context:
                        continue

                    yield JobResult(
                        company_name=card.get("company", ""),
                        job_title=card.get("title", ""),
                        job_url=card.get("url") or f"https://fr.indeed.com/viewjob?jk={jk}",
                        location=card.get("location", ""),
                        contract_type=card.get("contract", ""),
                        tool_context=context,
                        source=self.SOURCE,
                    )
                    count += 1

                if len(cards) < 15:
                    break
                start += 15
                if start >= self.MAX_PAGES * 15:
                    break
                time.sleep(self.DELAY)

            self.log.info("Indeed matched=%s scanned=%s", count, len(seen_jk))
            detail_ctx.close()
            browser.close()

    def _apply_resource_blocking(self, page):
        try:
            page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )
        except Exception:
            pass

    def _apply_stealth(self, ctx):
        ctx.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """
        )

    def _inject_cookies(self, ctx):
        domain_map = {
            "cf_clearance": ".indeed.com",
            "CTK": ".indeed.com",
            "JSESSIONID": "fr.indeed.com",
            "INDEED_CSRF_TOKEN": "fr.indeed.com",
            "LC": ".indeed.com",
            "CSRF": ".indeed.com",
        }
        for name, value in self._cookies_dict.items():
            domain = domain_map.get(name, ".indeed.com")
            try:
                ctx.add_cookies([{"name": name, "value": value, "domain": domain, "path": "/"}])
            except Exception:
                pass

    def _load_results_page(self, page, url: str) -> bool:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.SEARCH_TIMEOUT_MS)
        except Exception as e:
            self.log.warning("Indeed navigation failed for %s: %s", url, e)
            return False

        for _ in range(4):
            page.wait_for_timeout(1200)
            html = page.content()
            if "blocked - indeed" in html.lower() or "security check" in html.lower():
                continue
            if page.query_selector(self._CARD_SELECTORS):
                return True

        html = page.content()
        if "blocked - indeed" in html.lower() or "security check" in html.lower():
            self.log.warning("Indeed still blocked by Cloudflare for %s", url)
        return bool(page.query_selector(self._CARD_SELECTORS))

    def _parse_cards(self, html: str) -> list[dict]:
        soup = parse_html(html)
        cards = []

        for el in soup.select(self._CARD_SELECTORS):
            jk = el.get("data-jk") or ""
            if not jk:
                link = el.select_one("a[data-jk]")
                if link:
                    jk = link.get("data-jk", "")

            title_el = el.select_one("h2.jobTitle span[title], h2.jobTitle span, h2 a span")
            company_el = el.select_one(".companyName, [data-testid='company-name'], .css-1h7lukg")
            loc_el = el.select_one(".companyLocation, [data-testid='text-location']")
            link_el = el.select_one("a[data-jk]")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc = loc_el.get_text(strip=True) if loc_el else ""
            href = link_el.get("href", "") if link_el else ""
            snippet_el = el.select_one(".job-snippet, [data-testid='job-snippet']")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            if title and jk:
                cards.append(
                    {
                        "jk": jk,
                        "title": title,
                        "company": company,
                        "location": loc,
                        "url": f"https://fr.indeed.com{href}" if href.startswith("/") else href,
                        "contract": "",
                        "snippet": snippet,
                    }
                )
        return cards

    def _get_description_via_search_page(self, detail_page, tool: str, start: int, jk: str) -> str:
        try:
            url = f"{SEARCH_URL}?q={tool}&l=France&sort=date&start={start}&vjk={jk}"
            detail_page.goto(url, wait_until="domcontentloaded", timeout=self.DETAIL_TIMEOUT_MS)
            for _ in range(3):
                detail_page.wait_for_timeout(1000)
                html = detail_page.content()
                if "blocked - indeed" in html.lower() or "security check" in html.lower():
                    continue
                soup = parse_html(html)
                desc = soup.select_one(self._DESC_SEL)
                if desc:
                    return desc.get_text(" ", strip=True)
            return ""
        except Exception:
            return ""
