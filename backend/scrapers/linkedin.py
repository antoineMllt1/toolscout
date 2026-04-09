"""
LinkedIn public job search scraper (no authentication required).
Strategy:
  1. GET https://www.linkedin.com/jobs/search/?keywords=TOOL&location=France&start=N
     → Returns HTML with up to 25 job cards per page (data-entity-urn*=jobPosting)
  2. For each job ID: GET https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}
     → Public guest API returning full HTML including description — much less rate-limited
     → Parse .show-more-less-html__markup for description text
  3. Run extract_tool_context() on the description

No cookies or authentication needed. Stop on 429 to avoid IP ban.
"""
import time
import re
from typing import Iterator
from bs4 import BeautifulSoup
from .base import BaseScraper, JobResult

SEARCH_URL  = "https://www.linkedin.com/jobs/search/"
GUEST_URL   = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
DETAIL_URL  = "https://fr.linkedin.com/jobs/view/{job_id}"

LI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

LI_HEADERS = {
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.linkedin.com/jobs/search/",
}

DESC_SEL = (
    ".show-more-less-html__markup, "
    "[class*=description__text], "
    ".description__text, "
    "#job-details"
)


class LinkedInScraper(BaseScraper):
    SOURCE = "linkedin"
    DELAY  = 2.0  # respect rate limits

    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        # Replace session entirely with minimal headers — extra headers trigger LinkedIn's 999
        import requests as _req
        self.session = _req.Session()
        self.session.headers.clear()
        self.session.headers["User-Agent"] = LI_UA
        self._rate_limited = False

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        start    = 0
        count    = 0
        seen_ids: set[str] = set()

        while count < max_results and not self._rate_limited:
            params = {
                "keywords": tool,
                "location": "France",
                "f_TPR":    "r2592000",  # last 30 days
                "start":    start,
            }
            resp = self._get_with_429_check(SEARCH_URL, params=params)
            if not resp:
                break

            cards = self._parse_cards(resp.text)
            if not cards:
                break

            for card in cards:
                if count >= max_results or self._rate_limited:
                    return
                job_id = card.get("job_id", "")
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                description = self._fetch_description_guest(job_id)
                if not description:
                    continue

                context = self.extract_tool_context(description, tool)
                if not context:
                    continue

                time.sleep(self.DELAY)

                yield JobResult(
                    company_name=card.get("company", ""),
                    job_title=card.get("title", ""),
                    job_url=card.get("url", ""),
                    location=card.get("location", ""),
                    contract_type=card.get("contract", ""),
                    tool_context=context,
                    source=self.SOURCE,
                )
                count += 1

            if len(cards) < 10:
                break
            start += 25
            time.sleep(self.DELAY)

    def _get_with_429_check(self, url, **kwargs):
        """GET that stops on 429/999 (rate limit / bot detection) instead of retrying."""
        try:
            resp = self.session.get(url, timeout=12, **kwargs)
            if resp.status_code in (429, 999):
                print(f"[linkedin] Rate limited ({resp.status_code}) — stopping")
                self._rate_limited = True
                return None
            if resp.status_code >= 400:
                print(f"[linkedin] HTTP {resp.status_code} for {url}")
                return None
            return resp
        except Exception as e:
            if "429" in str(e) or "999" in str(e):
                print(f"[linkedin] Rate limited — stopping")
                self._rate_limited = True
            else:
                print(f"[linkedin] GET {url} failed: {e}")
            return None

    def _parse_cards(self, html: str) -> list[dict]:
        soup  = BeautifulSoup(html, "lxml")
        cards = []

        for el in soup.select("div[data-entity-urn*=jobPosting]"):
            urn    = el.get("data-entity-urn", "")
            job_id = urn.split(":")[-1] if urn else ""
            if not job_id:
                continue

            title_el   = el.select_one("h3.base-search-card__title, h3, [class*=title]")
            company_el = el.select_one("h4.base-search-card__subtitle, h4, [class*=company]")
            loc_el     = el.select_one(".job-search-card__location, [class*=location]")
            link_el    = el.select_one("a[href*='linkedin.com/jobs/view']")

            title   = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc     = loc_el.get_text(strip=True) if loc_el else ""
            url     = link_el["href"].split("?")[0] if link_el else DETAIL_URL.format(job_id=job_id)

            if title:
                cards.append({
                    "job_id":   job_id,
                    "title":    title,
                    "company":  company,
                    "location": loc,
                    "contract": "",
                    "url":      url,
                })
        return cards

    def _fetch_description_guest(self, job_id: str) -> str:
        """
        Use LinkedIn's public guest jobs API — returns full HTML with description.
        Much less rate-limited than the regular job view page.
        """
        url  = GUEST_URL.format(job_id=job_id)
        resp = self._get_with_429_check(url)
        if not resp:
            return ""

        soup = BeautifulSoup(resp.text, "lxml")

        desc_el = soup.select_one(DESC_SEL)
        if desc_el:
            return desc_el.get_text(" ", strip=True)

        # Fallback: JSON-LD description field
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                import json
                data = json.loads(script.string or "")
                desc = data.get("description", "")
                if desc and len(desc) > 100:
                    return re.sub(r"<[^>]+>", " ", desc)
            except Exception:
                pass

        return ""
