"""
HelloWork scraper — REST JSON API (no authentication required).
Strategy:
  1. POST to https://www.hellowork.com/fr-fr/api/jobs/search with JSON body
  2. Each hit includes a full description field — no detail page needed
  3. Parse description with extract_tool_context()

API discovered via DevTools:
  POST https://www.hellowork.com/fr-fr/api/jobs/search
  Headers: Content-Type: application/json, X-Requested-With: XMLHttpRequest
  Body: { "q": "TOOL", "l": "France", "page": 1, "results_per_page": 20 }
  Response: { "results": [...], "total": N, "nb_pages": N }

Job fields used:
  - title, company.name, location.label, contract_type.label, url, description
"""
import time
from typing import Iterator
from .base import BaseScraper, JobResult

SEARCH_URL = "https://www.hellowork.com/fr-fr/api/jobs/search"
BASE_URL    = "https://www.hellowork.com"

HW_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.hellowork.com/fr-fr/emploi/recherche.html",
    "Origin":  "https://www.hellowork.com",
}

CONTRACT_MAP = {
    "cdi":         "CDI",
    "cdd":         "CDD",
    "stage":       "Stage",
    "alternance":  "Alternance",
    "freelance":   "Freelance",
    "interim":     "Intérim",
    "vie":         "VIE",
}


class HelloWorkScraper(BaseScraper):
    SOURCE = "hellowork"
    DELAY  = 1.0

    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        self.session.headers.update(HW_HEADERS)

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        page  = 1
        count = 0
        seen_urls: set[str] = set()

        while count < max_results:
            payload = {
                "q":               tool,
                "l":               "France",
                "page":            page,
                "results_per_page": 20,
            }

            resp = self.safe_post(SEARCH_URL, payload)
            if not resp:
                break

            data     = resp.json()
            jobs     = data.get("results") or data.get("jobs") or []
            nb_pages = data.get("nb_pages") or data.get("nbPages") or 1

            if not jobs:
                # Try alternate response shape
                jobs = data.get("data", {}).get("results", [])

            if not jobs:
                print(f"[hellowork] No jobs in response (page {page}). Keys: {list(data.keys())}")
                break

            for job in jobs:
                if count >= max_results:
                    return

                description = self._extract_description(job)
                if not description:
                    continue

                context = self.extract_tool_context(description, tool)
                if not context:
                    continue

                url = self._extract_url(job)
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                yield JobResult(
                    company_name=self._extract_company(job),
                    job_title=job.get("title") or job.get("name") or "",
                    job_url=url,
                    location=self._extract_location(job),
                    contract_type=self._extract_contract(job),
                    tool_context=context,
                    source=self.SOURCE,
                )
                count += 1

            if page >= nb_pages:
                break
            page += 1
            self.sleep()

    def safe_post(self, url: str, payload: dict):
        try:
            resp = self.session.post(url, json=payload, timeout=12)
            resp.raise_for_status()
            return resp
        except Exception as e:
            print(f"[hellowork] POST {url} failed: {e}")
            return None

    def _extract_description(self, job: dict) -> str:
        for key in ("description", "job_description", "content", "text", "body"):
            v = job.get(key)
            if v and isinstance(v, str) and len(v) > 50:
                return v
        return ""

    def _extract_url(self, job: dict) -> str:
        url = job.get("url") or job.get("apply_url") or job.get("link") or ""
        if url and not url.startswith("http"):
            url = BASE_URL + url
        return url

    def _extract_company(self, job: dict) -> str:
        company = job.get("company") or {}
        if isinstance(company, dict):
            return company.get("name") or company.get("label") or ""
        return str(company)

    def _extract_location(self, job: dict) -> str:
        loc = job.get("location") or job.get("city") or {}
        if isinstance(loc, dict):
            return loc.get("label") or loc.get("name") or loc.get("city") or ""
        return str(loc) if loc else ""

    def _extract_contract(self, job: dict) -> str:
        ct = job.get("contract_type") or job.get("contract") or {}
        if isinstance(ct, dict):
            raw = ct.get("label") or ct.get("name") or ""
        else:
            raw = str(ct)
        return CONTRACT_MAP.get(raw.lower(), raw)
