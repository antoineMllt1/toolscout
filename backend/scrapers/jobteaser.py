"""
Jobteaser scraper.

Uses Playwright with a small stealth layer, waits for result cards explicitly,
then opens a limited number of detail pages to extract the job description.
"""
import time
from typing import Iterator
from urllib.parse import urljoin

from .base import BaseScraper, JobResult, parse_html

BASE_URL = "https://www.jobteaser.com"
SEARCH_URL = "https://www.jobteaser.com/fr/job-offers"

PLAYWRIGHT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class JobteaserScraper(BaseScraper):
    SOURCE = "jobteaser"
    DELAY = 0.35
    MAX_PAGES = 20
    MAX_SCANNED_JOBS = 120
    MAX_DURATION = 70
    SEARCH_TIMEOUT_MS = 15000
    DETAIL_TIMEOUT_MS = 7000

    _RESULT_SELECTOR = "[class*=JobAdCard_main], a[href*='/job-offers/']"
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

    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        self.cookies_list: list[dict] = []
        if cookies:
            for name, value in cookies.items():
                self.cookies_list.append(
                    {
                        "name": name,
                        "value": value,
                        "domain": ".jobteaser.com",
                        "path": "/",
                    }
                )

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
                user_agent=PLAYWRIGHT_UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8"},
            )
            self._apply_stealth(ctx)
            if self.cookies_list:
                try:
                    ctx.add_cookies(self.cookies_list)
                except Exception:
                    pass

            page = ctx.new_page()
            detail_page = ctx.new_page()
            self._apply_resource_blocking(page)
            self._apply_resource_blocking(detail_page)

            started_at = time.monotonic()
            jobs = self._load_search_results(page, tool, max_results, started_at)
            self.log.info("Jobteaser initial jobs=%s for tool=%s", len(jobs), tool)

            count = 0
            seen_urls: set[str] = set()

            for idx, job in enumerate(jobs):
                if count >= max_results:
                    break
                if idx >= self.MAX_SCANNED_JOBS:
                    break
                if time.monotonic() - started_at > self.MAX_DURATION:
                    self.log.warning("Jobteaser time budget reached after %.1fs", time.monotonic() - started_at)
                    break

                url = job.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                if not self._should_fetch_detail(job, tool):
                    continue

                description = self._fetch_detail_playwright(detail_page, url)
                time.sleep(self.DELAY)
                if not description:
                    continue

                context = self.extract_search_context(description, tool, job.get("title", ""))
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

            self.log.info("Jobteaser matched=%s scanned=%s", count, len(seen_urls))
            browser.close()

    def _apply_stealth(self, ctx):
        ctx.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """
        )

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

    def _load_search_results(self, page, tool: str, max_results: int, started_at: float) -> list[dict]:
        jobs: list[dict] = []
        pages_done = 0
        total_pages = self.MAX_PAGES
        candidate_target = max(max_results * 3, max_results + 12)
        while pages_done < min(total_pages, self.MAX_PAGES):
            if time.monotonic() - started_at > self.MAX_DURATION:
                return jobs

            url = f"{SEARCH_URL}?lang=fr&country%5B%5D=FR&page={pages_done + 1}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.SEARCH_TIMEOUT_MS)
            except Exception as e:
                self.log.warning("Jobteaser navigation failed for %s: %s", url, e)
                break
            if not self._wait_for_results(page):
                break

            page_jobs = self._parse_results_html(page.content())
            self.log.info("Jobteaser generic page=%s cards=%s", pages_done + 1, len(page_jobs))
            if not page_jobs:
                break
            total_pages = self._extract_total_pages(page.content()) or total_pages
            jobs.extend(page_jobs)
            pages_done += 1
            candidate_count = sum(1 for job in jobs if self._should_fetch_detail(job, tool))
            if candidate_count >= candidate_target:
                break

        deduped = []
        seen_urls: set[str] = set()
        for job in jobs:
            url = job.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(job)
        return deduped

    def _extract_total_pages(self, html: str) -> int:
        soup = parse_html(html)
        page_links = soup.select("a[aria-label*='page']")
        page_numbers = []
        for link in page_links:
            label = link.get("aria-label", "")
            digits = "".join(ch for ch in label if ch.isdigit())
            if digits:
                try:
                    page_numbers.append(int(digits))
                except ValueError:
                    continue
        return max(page_numbers) if page_numbers else 0

    def _get_search_terms(self, tool: str) -> list[str]:
        return [tool]

    def _wait_for_results(self, page) -> bool:
        for _ in range(8):
            page.wait_for_timeout(1250)
            html = page.content().lower()
            if "just a moment" in html:
                continue
            if page.query_selector(self._RESULT_SELECTOR):
                return True
        html = page.content().lower()
        if "just a moment" in html:
            self.log.warning("Jobteaser still blocked by Cloudflare on search page")
        return bool(page.query_selector(self._RESULT_SELECTOR))

    def _parse_results_html(self, html: str) -> list[dict]:
        soup = parse_html(html)
        cards = soup.select("[class*=JobAdCard_main], article:has(a[href*='/job-offers/']), li:has(a[href*='/job-offers/'])")
        jobs = []

        for card in cards:
            link_el = card.select_one("a[class*=JobAdCard_link]")
            if not link_el:
                link_el = card.select_one("a[href*='/job-offers/']")
            if not link_el:
                continue

            title = link_el.get_text(strip=True)
            href = link_el.get("href", "")
            url = urljoin(BASE_URL, href) if href else ""

            company = ""
            img_el = card.select_one("img[alt]")
            if img_el:
                company = img_el.get("alt", "")
            if not company:
                p_el = card.select_one("p[class*=sk-Text]")
                if p_el:
                    company = p_el.get_text(strip=True)

            spans = card.select("span[class*=sk-Text], [class*=Tag], [class*=meta]")
            contract = spans[0].get_text(strip=True) if len(spans) > 0 else ""
            location = spans[1].get_text(strip=True) if len(spans) > 1 else ""
            card_text = card.get_text(" ", strip=True)

            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "url": url,
                    "location": location,
                    "contract": contract,
                    "card_text": card_text,
                }
            )
        return jobs

    def _should_fetch_detail(self, job: dict, tool: str) -> bool:
        query = self._normalize_for_match(tool)
        haystack = self._normalize_for_match(
            " ".join(
                [
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("contract", ""),
                    job.get("card_text", ""),
                ]
            )
        )
        if not query:
            return True
        if query in haystack:
            return True

        tokens = [token for token in query.split() if len(token) > 2]
        if not tokens:
            return True

        hits = sum(token in haystack for token in tokens)
        return hits >= max(1, len(tokens) - 1)

    def _fetch_detail_playwright(self, page, url: str) -> str:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.DETAIL_TIMEOUT_MS)
            try:
                page.wait_for_selector(self._DESC_SELECTORS, timeout=2200)
            except Exception:
                page.wait_for_timeout(500)

            soup = parse_html(page.content())
            desc_el = soup.select_one(self._DESC_SELECTORS)
            if desc_el:
                return desc_el.get_text(" ", strip=True)

            main = soup.select_one("main")
            if main:
                sections = main.find_all("section")
                if sections:
                    longest = max(sections, key=lambda s: len(s.get_text()))
                    if len(longest.get_text()) > 200:
                        return longest.get_text(" ", strip=True)
                return main.get_text(" ", strip=True)
        except Exception as e:
            self.log.warning("Detail fetch failed for %s: %s", url, e)
        return ""
