"""
Indeed France scraper — Playwright-based with CF cookie injection.
Strategy:
  1. Inject user's cf_clearance cookie into Playwright context
  2. Load search results page (wait_until='load')
  3. Click each job card → description loads in side panel
  4. Extract #jobDescriptionText for tool mention analysis

Without cf_clearance (first-time use), Playwright handles the CF challenge natively.
The cf_clearance cookie can be provided via /api/config/cookies in the UI.
"""
import json
import time
from typing import Iterator
from bs4 import BeautifulSoup
from .base import BaseScraper, JobResult

SEARCH_URL = "https://fr.indeed.com/emplois"
VIEWJOB_URL = "https://fr.indeed.com/viewjob?jk={jk}"

INDEED_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)

INDEED_COOKIES_SCHEMA = [
    # (cookie_name, domain, description)
    ("cf_clearance",      ".indeed.com",    "Cloudflare clearance — expires 2027"),
    ("CTK",               ".indeed.com",    "Client tracking key — expires 2027"),
    ("JSESSIONID",        "fr.indeed.com",  "Session ID"),
    ("INDEED_CSRF_TOKEN", "fr.indeed.com",  "CSRF token"),
    ("LC",                ".indeed.com",    "Country: co=FR"),
]


class IndeedScraper(BaseScraper):
    SOURCE = "indeed"
    DELAY  = 1.0

    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        self._cookies_dict = cookies or {}

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        yield from self._search_playwright(tool, max_results)

    def _search_playwright(self, tool: str, max_results: int) -> Iterator[JobResult]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            print("[indeed] Playwright not installed.")
            return

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(
                user_agent=INDEED_UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1440, "height": 900},
                extra_http_headers={
                    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
                    "Sec-CH-UA": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
                    "Sec-CH-UA-Platform": '"Windows"',
                    "Sec-CH-UA-Mobile": "?0",
                },
            )

            # Inject user cookies (helps bypass CF immediately)
            self._inject_cookies(ctx)

            page = ctx.new_page()
            count   = 0
            start   = 0
            seen_jk: set[str] = set()

            while count < max_results:
                url = f"{SEARCH_URL}?q={tool}&l=France&sort=date&start={start}"
                try:
                    page.goto(url, wait_until="load", timeout=35000)
                    page.wait_for_timeout(2500)
                except PWTimeout:
                    print("[indeed] Page load timeout, trying domcontentloaded...")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(3000)
                    except Exception as e:
                        print(f"[indeed] Navigation failed: {e}")
                        break

                # Parse job cards
                html  = page.content()
                cards = self._parse_cards(html)

                if not cards:
                    break

                for card in cards:
                    if count >= max_results:
                        break
                    jk = card.get("jk", "")
                    if not jk or jk in seen_jk:
                        continue
                    seen_jk.add(jk)

                    # Click the card to load description in side panel
                    description = self._get_description_via_click(page, jk)
                    if not description:
                        # Fallback: navigate directly
                        description = self._get_description_via_viewjob(page, jk)

                    if not description:
                        continue

                    context = self.extract_tool_context(description, tool)
                    if not context:
                        continue

                    yield JobResult(
                        company_name=card.get("company", ""),
                        job_title=card.get("title", ""),
                        job_url=f"https://fr.indeed.com/rc/clk?jk={jk}",
                        location=card.get("location", ""),
                        contract_type=card.get("contract", ""),
                        tool_context=context,
                        source=self.SOURCE,
                    )
                    count += 1

                if len(cards) < 15:
                    break
                start += 15
                time.sleep(self.DELAY)

            browser.close()

    def _inject_cookies(self, ctx):
        """Inject saved cookies into Playwright context."""
        domain_map = {
            "cf_clearance":      ".indeed.com",
            "CTK":               ".indeed.com",
            "JSESSIONID":        "fr.indeed.com",
            "INDEED_CSRF_TOKEN": "fr.indeed.com",
            "LC":                ".indeed.com",
            "CSRF":              ".indeed.com",
        }
        for name, value in self._cookies_dict.items():
            domain = domain_map.get(name, ".indeed.com")
            try:
                ctx.add_cookies([{
                    "name": name, "value": value,
                    "domain": domain, "path": "/",
                }])
            except Exception:
                pass

    def _parse_cards(self, html: str) -> list[dict]:
        soup  = BeautifulSoup(html, "lxml")
        cards = []
        for el in soup.select("div[data-jk], div.job_seen_beacon"):
            jk = el.get("data-jk") or ""
            if not jk:
                link = el.select_one("a[data-jk]")
                if link:
                    jk = link.get("data-jk", "")

            title_el   = el.select_one("h2.jobTitle span[title], h2.jobTitle span, h2 a span")
            company_el = el.select_one(".companyName, [data-testid='company-name'], .css-1h7lukg")
            loc_el     = el.select_one(".companyLocation, [data-testid='text-location']")

            title   = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc     = loc_el.get_text(strip=True) if loc_el else ""

            if title and jk:
                cards.append({
                    "jk": jk, "title": title, "company": company,
                    "location": loc, "contract": "",
                })
        return cards

    _DESC_SEL = (
        "#jobDescriptionText, "
        ".jobsearch-jobDescriptionText, "
        "[data-testid='jobsearch-JobComponent-description'], "
        ".job-description, "
        "#job-details-content, "
        "[id*='jobDescriptionText'], "
        ".jobDescriptionContent"
    )

    def _get_description_via_click(self, page, jk: str) -> str:
        """Click the job card to load description in the side panel."""
        try:
            card = page.query_selector(f'div[data-jk="{jk}"]')
            if not card:
                card = page.query_selector(f'a[data-jk="{jk}"]')
            if not card:
                return ""
            card.click()
            try:
                page.wait_for_selector(self._DESC_SEL, timeout=6000)
            except Exception:
                page.wait_for_timeout(1500)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            desc = soup.select_one(self._DESC_SEL)
            return desc.get_text(" ", strip=True) if desc else ""
        except Exception:
            return ""

    def _get_description_via_viewjob(self, page, jk: str) -> str:
        """Navigate to the full job page as fallback."""
        try:
            page.goto(VIEWJOB_URL.format(jk=jk), wait_until="load", timeout=20000)
            try:
                page.wait_for_selector(self._DESC_SEL, timeout=6000)
            except Exception:
                page.wait_for_timeout(1500)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            desc = soup.select_one(self._DESC_SEL)
            return desc.get_text(" ", strip=True) if desc else ""
        except Exception:
            return ""
