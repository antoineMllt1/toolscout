"""
LinkedIn public job search scraper (no authentication required).
Strategy:
  1. GET https://www.linkedin.com/jobs/search/?keywords=TOOL&location=France&start=N
     -> Returns HTML with up to 25 job cards per page (data-entity-urn*=jobPosting)
  2. For each job ID: GET https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}
     -> Public guest API returning full HTML including description
  3. Run extract_tool_context() on the description

No cookies or authentication needed. Stop on 429/999 to avoid IP bans.
"""
import random
import re
import time
from typing import Iterator

from .base import BaseScraper, JobResult, parse_html

SEARCH_URL = "https://www.linkedin.com/jobs/search/"
GUEST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
DETAIL_URL = "https://www.linkedin.com/jobs/view/{job_id}"

_LI_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

DESC_SEL = (
    ".show-more-less-html__markup, "
    "[class*=description__text], "
    ".description__text, "
    "#job-details"
)


class LinkedInScraper(BaseScraper):
    SOURCE = "linkedin"
    DELAY = 1.2          # base delay between requests
    DELAY_JITTER = 0.6   # ± random jitter added on top
    MAX_PAGES = 6
    MAX_DURATION = 90

    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        # Keep the session minimal; extra headers tend to trigger LinkedIn anti-bot.
        import requests as _req

        self.session = _req.Session()
        self.session.headers.clear()
        self.session.headers["User-Agent"] = random.choice(_LI_UAS)
        self._rate_limited = False

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        count = 0
        seen_ids: set[str] = set()
        started_at = time.monotonic()

        for search_term in self._get_search_terms(tool):
            start = 0

            while count < max_results and not self._rate_limited:
                if time.monotonic() - started_at > self.MAX_DURATION:
                    self.log.warning("LinkedIn time budget reached after %.1fs", time.monotonic() - started_at)
                    return
                params = {
                    "keywords": search_term,
                    "location": "France",
                    "f_TPR": "r2592000",
                    "start": start,
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
                    time.sleep(self.DELAY + random.uniform(0, self.DELAY_JITTER))
                    if not description:
                        continue

                    context = self.extract_search_context(description, tool, card.get("title", ""))
                    if not context:
                        continue

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
                    if time.monotonic() - started_at > self.MAX_DURATION:
                        self.log.warning("LinkedIn time budget reached after %.1fs", time.monotonic() - started_at)
                        return

                if len(cards) < 10 or (start // 25) + 1 >= self.MAX_PAGES:
                    break

                start += 25
                time.sleep(self.DELAY + random.uniform(0, self.DELAY_JITTER))

            if count >= max_results or self._rate_limited:
                break

    def _get_search_terms(self, tool: str) -> list[str]:
        tool_lower = tool.lower().strip()
        aliases = self.get_aliases(tool)
        alias_terms = [alias for alias in aliases if alias.lower() != tool_lower]

        if tool_lower in {"make", "bubble", "monday", "stitch"} and alias_terms:
            return list(dict.fromkeys(alias_terms))
        return [tool]

    def _get_with_429_check(self, url, **kwargs):
        try:
            resp = self.session.get(url, timeout=12, **kwargs)
            if resp.status_code in (429, 999):
                self.log.warning("Rate limited by LinkedIn (HTTP %s); stopping", resp.status_code)
                self._rate_limited = True
                return None
            if resp.status_code >= 400:
                self.log.warning("HTTP %s for %s", resp.status_code, url)
                return None
            return resp
        except Exception as e:
            if "429" in str(e) or "999" in str(e):
                self.log.warning("Rate limited by LinkedIn; stopping")
                self._rate_limited = True
            else:
                self.log.warning("GET %s failed: %s", url, e)
            return None

    def _parse_cards(self, html: str) -> list[dict]:
        soup = parse_html(html)
        cards = []

        for el in soup.select("div[data-entity-urn*=jobPosting]"):
            urn = el.get("data-entity-urn", "")
            job_id = urn.split(":")[-1] if urn else ""
            if not job_id:
                continue

            title_el = el.select_one("h3.base-search-card__title, h3, [class*=title]")
            company_el = el.select_one("h4.base-search-card__subtitle, h4, [class*=company]")
            loc_el = el.select_one(".job-search-card__location, [class*=location]")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc = loc_el.get_text(strip=True) if loc_el else ""
            url = DETAIL_URL.format(job_id=job_id)

            if title:
                cards.append(
                    {
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "location": loc,
                        "contract": "",
                        "url": url,
                    }
                )
        return cards

    def _fetch_description_guest(self, job_id: str) -> str:
        url = GUEST_URL.format(job_id=job_id)
        resp = self._get_with_429_check(url)
        if not resp:
            return ""

        soup = parse_html(resp.text)

        desc_el = soup.select_one(DESC_SEL)
        if desc_el:
            return desc_el.get_text(" ", strip=True)

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
