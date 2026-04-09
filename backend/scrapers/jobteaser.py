"""
Jobteaser scraper — Playwright-based (pure SSR, no data API).
Structure discovered via DevTools:
  - Search: https://www.jobteaser.com/fr/job-offers?query=TOOL
  - Cards: [class*=JobAdCard_main]
  - Title: a.JobAdCard_link__* (href = /fr/job-offers/{uuid}-{slug})
  - Company: p.sk-Text (first), img[alt]
  - Contract: span.sk-Text (1st after title)
  - Location: span.sk-Text (2nd after title)
  - Detail URL: https://www.jobteaser.com{href}
"""
import re
import time
from typing import Iterator
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper, JobResult

BASE_URL   = "https://www.jobteaser.com"
SEARCH_URL = "https://www.jobteaser.com/fr/job-offers"

PLAYWRIGHT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class JobteaserScraper(BaseScraper):
    SOURCE = "jobteaser"
    DELAY  = 1.5

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        yield from self._search_playwright(tool, max_results)

    def _search_playwright(self, tool: str, max_results: int) -> Iterator[JobResult]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[jobteaser] Playwright not installed. Run: pip install playwright && playwright install chromium")
            return

        all_jobs: list[dict] = []
        cf_cookies: list[dict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(
                user_agent=PLAYWRIGHT_UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1280, "height": 900},
            )
            # Inject user-provided cookies if any
            if self.cookies_list:
                ctx.add_cookies(self.cookies_list)

            page = ctx.new_page()

            try:
                page.goto(
                    f"{SEARCH_URL}?query={tool}&lang=fr&country%5B%5D=FR",
                    wait_until="networkidle",
                    timeout=30000,
                )
                page.wait_for_timeout(2000)

                # Collect cookies from the Playwright session for reuse in requests
                cf_cookies = ctx.cookies()

                # Scrape first page
                html = page.content()
                jobs = self._parse_results_html(html)
                all_jobs.extend(jobs)

                # Paginate — try clicking "next" or scrolling
                pages_done = 1
                while len(all_jobs) < max_results and pages_done < 5:
                    try:
                        next_btn = page.query_selector(
                            'button[aria-label*="suivant"], button[aria-label*="next"], '
                            '[data-testid="pagination-next"], a[rel="next"]'
                        )
                        if not next_btn:
                            break
                        next_btn.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        page.wait_for_timeout(1500)
                        new_jobs = self._parse_results_html(page.content())
                        if not new_jobs:
                            break
                        all_jobs.extend(new_jobs)
                        pages_done += 1
                    except Exception:
                        break

            except Exception as e:
                print(f"[jobteaser] Playwright error: {e}")

            browser.close()

        # Re-open browser to fetch detail pages (CF blocks requests but not Playwright)
        results: list[JobResult] = []
        seen_urls: set[str] = set()
        count = 0

        with sync_playwright() as p2:
            b2 = p2.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            ctx2 = b2.new_context(
                user_agent=PLAYWRIGHT_UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1280, "height": 900},
            )
            # Reuse CF cookies from first session
            if cf_cookies:
                try:
                    ctx2.add_cookies(cf_cookies)
                except Exception:
                    pass

            page2 = ctx2.new_page()

            for job in all_jobs:
                if count >= max_results:
                    break
                url = job.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                description = self._fetch_detail_playwright(page2, url)
                time.sleep(self.DELAY)

                context = self.extract_tool_context(description, tool)
                if not context:
                    continue

                yield JobResult(
                    company_name=job.get("company", ""),
                    job_title=job.get("title", ""),
                    job_url=url,
                    location=job.get("location", ""),
                    contract_type=job.get("contract", ""),
                    tool_context=context,
                    source=self.SOURCE,
                )
                count += 1

            b2.close()

    def _parse_results_html(self, html: str) -> list[dict]:
        """Parse job cards from rendered Jobteaser HTML."""
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("[class*=JobAdCard_main]")
        jobs  = []

        for card in cards:
            # Title + URL
            link_el = card.select_one("a[class*=JobAdCard_link]")
            if not link_el:
                link_el = card.select_one("a[href*='/job-offers/']")
            if not link_el:
                continue

            title = link_el.get_text(strip=True)
            href  = link_el.get("href", "")
            url   = urljoin(BASE_URL, href) if href else ""

            # Company: img alt or first p.sk-Text
            company = ""
            img_el = card.select_one("img[alt]")
            if img_el:
                company = img_el.get("alt", "")
            if not company:
                p_el = card.select_one("p[class*=sk-Text]")
                if p_el:
                    company = p_el.get_text(strip=True)

            # Contract + Location: span.sk-Text (in order)
            spans = card.select("span[class*=sk-Text]")
            contract = spans[0].get_text(strip=True) if len(spans) > 0 else ""
            location = spans[1].get_text(strip=True) if len(spans) > 1 else ""

            jobs.append({
                "title":    title,
                "company":  company,
                "url":      url,
                "location": location,
                "contract": contract,
            })

        return jobs

    # CSS selectors for the job description block (ordered by specificity)
    _DESC_SELECTORS = (
        "[class*=Description_main], "
        "[class*=Description_body], "
        "[class*=JobAdDescription], "
        "[class*=jobDescription], "
        "[class*=description__content], "
        "[class*=job-description], "
        "section[class*=description], "
        "div[class*=description]"
    )

    def _fetch_detail_playwright(self, page, url: str) -> str:
        """
        Fetch job detail page with Playwright.
        Jobteaser is a SPA (Next.js) — after navigation, the description block
        renders asynchronously; we must wait for the selector, not just page load.
        """
        try:
            # Use 'load' — networkidle never fires on CF challenge pages (infinite background XHR).
            # After CF cookies bypass the challenge, 'load' + wait_for_selector is sufficient.
            page.goto(url, wait_until="load", timeout=20000)
            # Wait for the description block to render (SPA async hydration)
            try:
                page.wait_for_selector(self._DESC_SELECTORS, timeout=10000)
            except Exception:
                page.wait_for_timeout(1500)  # fallback generic wait

            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            # Try each description selector in order
            desc_el = soup.select_one(self._DESC_SELECTORS)
            if desc_el:
                return desc_el.get_text(" ", strip=True)

            # Last resort: full <main> text (noisy but better than nothing)
            main = soup.select_one("main")
            if main:
                # Remove nav/header noise by targeting the largest <section>
                sections = main.find_all("section")
                if sections:
                    longest = max(sections, key=lambda s: len(s.get_text()))
                    if len(longest.get_text()) > 200:
                        return longest.get_text(" ", strip=True)
                return main.get_text(" ", strip=True)
        except Exception as e:
            print(f"[jobteaser] detail error for {url}: {e}")
        return ""

    # Store cookies list for ctx.add_cookies()
    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        self.cookies_list: list[dict] = []
        if cookies:
            for name, value in cookies.items():
                self.cookies_list.append({
                    "name": name, "value": value,
                    "domain": ".jobteaser.com", "path": "/",
                })
