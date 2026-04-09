"""
Welcome to the Jungle scraper — uses Algolia search API.
Credentials extracted from window.env in the public HTML:
  ALGOLIA_APPLICATION_ID: CSEKHVMS53
  ALGOLIA_API_KEY_CLIENT: 4bd8f6215d0cc52b26430765769e65a0
  ALGOLIA_JOBS_INDEX_PREFIX: wttj_jobs_production
Index: wttj_jobs_production_fr

Method: POST https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX}/query
Required headers: Origin + Referer pointing to welcometothejungle.com
"""
import re
import time
from typing import Iterator
from bs4 import BeautifulSoup
from .base import BaseScraper, JobResult

ALGOLIA_APP_ID  = "CSEKHVMS53"
ALGOLIA_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
ALGOLIA_INDEX   = "wttj_jobs_production_fr"
ALGOLIA_URL     = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
JOB_PAGE_URL    = "https://www.welcometothejungle.com/fr/companies/{org}/jobs/{slug}"

ALGOLIA_HEADERS = {
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "Content-Type": "application/json",
    "Origin": "https://www.welcometothejungle.com",
    "Referer": "https://www.welcometothejungle.com/",
}

CONTRACT_LABELS = {
    "full_time":   "CDI",
    "part_time":   "Temps partiel",
    "internship":  "Stage",
    "freelance":   "Freelance",
    "vie":         "VIE",
    "apprenticeship": "Alternance",
    "temporary":   "CDD",
}


def _fetch_algolia_credentials() -> tuple[str, str]:
    """
    Fallback: re-extract API key from the public HTML in case it changes.
    Returns (app_id, api_key).
    """
    import requests as _req
    try:
        r = _req.get(
            "https://www.welcometothejungle.com/fr/jobs",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
            },
            timeout=10,
        )
        m_id  = re.search(r'"ALGOLIA_APPLICATION_ID"\s*:\s*"([^"]+)"', r.text)
        m_key = re.search(r'"ALGOLIA_API_KEY_CLIENT"\s*:\s*"([^"]+)"', r.text)
        if m_id and m_key:
            return m_id.group(1), m_key.group(1)
    except Exception:
        pass
    return ALGOLIA_APP_ID, ALGOLIA_API_KEY


class WTTJScraper(BaseScraper):
    SOURCE = "wttj"
    DELAY = 1.2

    def __init__(self, cookies: dict | None = None):
        super().__init__(cookies)
        # Override headers for Algolia (different from browser headers)
        self.session.headers.update(ALGOLIA_HEADERS)
        self._app_id = ALGOLIA_APP_ID
        self._api_key = ALGOLIA_API_KEY

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        page = 0
        count = 0
        seen_urls: set[str] = set()

        # For ambiguous short words like "make", enrich the query
        search_query = self._build_query(tool)

        while count < max_results:
            payload = {
                "query": search_query,
                "hitsPerPage": min(30, max_results * 3),  # Fetch more, many will be filtered
                "page": page,
                "attributesToRetrieve": [
                    "name", "slug", "organization", "offices",
                    "contract_type", "profile", "key_missions",
                    "summary", "reference", "published_at_date",
                ],
            }

            resp = self._algolia_post(payload)
            if not resp:
                self._app_id, self._api_key = _fetch_algolia_credentials()
                resp = self._algolia_post(payload)
                if not resp:
                    break

            hits = resp.get("hits", [])
            nb_pages = resp.get("nbPages", 1)

            if not hits:
                break

            for hit in hits:
                if count >= max_results:
                    return

                result = self._parse_hit(hit, tool)
                if not result:
                    continue

                # Deduplicate by job URL
                if result.job_url and result.job_url in seen_urls:
                    continue
                if result.job_url:
                    seen_urls.add(result.job_url)

                yield result
                count += 1

            if page + 1 >= nb_pages:
                break

            page += 1
            self.sleep()

    def _build_query(self, tool: str) -> str:
        """
        Build the Algolia search query for a given tool.
        For ambiguous tools, we add OR-like terms by running multiple queries
        OR we use the main alias (Algolia does full-text, so 'make' finds job
        descriptions mentioning 'make' — context filtering handles false positives).
        """
        tool_lower = tool.lower().strip()
        # Use the most specific/recognizable alias as the search term
        primary: dict[str, str] = {
            "make":    "make",          # broad — context filter removes false positives
            "powerbi": "Power BI",
            "notion":  "notion",
            "bubble":  "bubble.io",
            "monday":  "monday.com",
        }
        return primary.get(tool_lower, tool)

    def _algolia_post(self, payload: dict) -> dict | None:
        url = f"https://{self._app_id}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
        self.session.headers["X-Algolia-API-Key"] = self._api_key
        self.session.headers["X-Algolia-Application-Id"] = self._app_id

        resp = None
        try:
            resp = self.session.post(url, json=payload, timeout=12)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            code = resp.status_code if resp else "?"
            self.log.warning("Algolia error (HTTP %s): %s", code, e)
            return None

    def _parse_hit(self, hit: dict, tool: str) -> JobResult | None:
        # Concatenate all textual fields for context extraction
        def _to_str(v) -> str:
            if isinstance(v, list):
                return " ".join(str(x) for x in v if x)
            return str(v) if v else ""

        profile   = _to_str(hit.get("profile"))
        missions  = _to_str(hit.get("key_missions"))
        summary   = _to_str(hit.get("summary"))
        full_text = " ".join(filter(None, [profile, missions, summary]))

        context = self.extract_tool_context(full_text, tool)
        if not context:
            return None  # Only keep jobs that actually mention the tool

        org   = hit.get("organization") or {}
        offices = hit.get("offices") or []
        location = ""
        if offices:
            city    = offices[0].get("city", "")
            country = offices[0].get("country", "")
            location = city if city else country

        org_slug = org.get("slug", "")
        job_slug = hit.get("slug", "")
        job_url  = JOB_PAGE_URL.format(org=org_slug, slug=job_slug) if org_slug and job_slug else ""

        raw_contract = hit.get("contract_type", "")
        contract = CONTRACT_LABELS.get(raw_contract, raw_contract.replace("_", " ").title())

        return JobResult(
            company_name=org.get("name", ""),
            job_title=hit.get("name", ""),
            job_url=job_url,
            location=location,
            contract_type=contract,
            tool_context=context,
            source=self.SOURCE,
        )
