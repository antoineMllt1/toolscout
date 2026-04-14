import logging
import re
import time
import requests
from dataclasses import dataclass, field
from typing import Iterator, Optional

from bs4 import BeautifulSoup

# Tool aliases — search also finds alternate names
TOOL_ALIASES: dict[str, list[str]] = {
    "make": ["make", "make.com", "integromat"],
    "powerbi": ["power bi", "powerbi", "microsoft power bi", "power-bi"],
    "n8n": ["n8n"],
    "zapier": ["zapier"],
    "airtable": ["airtable"],
    "notion": ["notion"],
    "hubspot": ["hubspot", "hub spot"],
    "salesforce": ["salesforce", "sfdc"],
    "tableau": ["tableau"],
    "looker": ["looker", "looker studio"],
    "dbt": ["dbt", "data build tool"],
    "airflow": ["airflow", "apache airflow"],
    "databricks": ["databricks"],
    "snowflake": ["snowflake"],
    "fivetran": ["fivetran"],
    "stitch": ["stitch", "stitch data"],
    "retool": ["retool"],
    "bubble": ["bubble.io", "bubble"],
    "webflow": ["webflow"],
    "amplitude": ["amplitude"],
    "mixpanel": ["mixpanel"],
    "segment": ["segment"],
    "metabase": ["metabase"],
    "grafana": ["grafana"],
    "domo": ["domo"],
    "monday": ["monday.com", "monday"],
    "jira": ["jira", "atlassian jira"],
    "confluence": ["confluence"],
    "figma": ["figma"],
    "miro": ["miro"],
}

# Ambiguous tool names that need tech-context check to avoid false positives.
# If the tool name is here, we require at least one tech signal in the context.
AMBIGUOUS_TOOLS = {
    "make",    # "make" is also a common English word / "make up" / "make my"
    "bubble",  # could be "bubble" used informally
    "segment", # could be "market segment"
    "notion",  # uncommon but could be used in general sense
    "monday",  # "monday morning" etc.
    "stitch",  # sewing term
}

# Keywords that confirm a tech/software context when tool name is ambiguous
TECH_SIGNALS = re.compile(
    r"(?i)\b("
    r"automation|workflow|no.code|nocode|outil|intégration|integration|"
    r"api|saas|crm|erp|logiciel|software|platform|données|data|"
    r"script|pipeline|trigger|webhook|zap|scénario|scenario|outil"
    r")\b"
)

AMBIGUOUS_TOOL_SIGNALS: dict[str, re.Pattern[str]] = {
    "make": re.compile(
        r"(?i)\b("
        r"make\.com|integromat|automation|workflow|webhook|scenario|"
        r"module|no.code|nocode|zapier|n8n|crm|api|integration"
        r")\b"
    ),
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-CH-UA": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}

try:
    import lxml  # noqa: F401

    HTML_PARSER = "lxml"
except Exception:
    HTML_PARSER = "html.parser"


@dataclass
class JobResult:
    company_name: str
    job_title: str
    job_url: str
    location: str = ""
    contract_type: str = ""
    tool_context: list = field(default_factory=list)
    source: str = ""


class BaseScraper:
    SOURCE = "base"
    DELAY = 1.5  # seconds between requests

    def __init__(self, cookies: dict | None = None):
        self.log = logging.getLogger(f"toolscout.scrapers.{self.SOURCE}")
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if cookies:
            for k, v in cookies.items():
                self.session.cookies.set(k, v)

    def search(self, tool: str, max_results: int = 50) -> Iterator[JobResult]:
        raise NotImplementedError

    def get_aliases(self, tool: str) -> list[str]:
        tool_lower = tool.lower().strip()
        for key, aliases in TOOL_ALIASES.items():
            if tool_lower == key or tool_lower in aliases:
                return aliases
        return [tool_lower]

    def extract_tool_context(self, text: str, tool: str) -> list[str]:
        """
        Find sentences/bullet points in the job description that mention the tool.
        Returns up to 4 relevant excerpts. No AI — pure regex + string matching.

        For ambiguous tool names (e.g. 'make'), we require at least one tech signal
        in the same chunk to avoid false positives like 'Make Up' or 'Make My Lemonade'.
        """
        if not text:
            return []

        aliases = self.get_aliases(tool)
        tool_lower = tool.lower().strip()

        # Build regex that matches any alias (word boundary)
        patterns = [re.escape(a) for a in aliases]
        combined = re.compile(r"(?i)\b(" + "|".join(patterns) + r")\b")

        is_ambiguous = tool_lower in AMBIGUOUS_TOOLS
        signal_pattern = AMBIGUOUS_TOOL_SIGNALS.get(tool_lower, TECH_SIGNALS)

        # Split text into sentences/bullets
        chunks = re.split(r"[\n•\-–—]|(?<=[.!?])\s+", text)
        relevant = []

        for chunk in chunks:
            stripped = chunk.strip()
            if not combined.search(stripped):
                continue
            if not (15 < len(stripped) < 500):
                continue

            # For ambiguous tools: require a tech signal in this chunk OR adjacent text
            if is_ambiguous:
                # Extra check: the tool name must appear as a standalone tech tool
                # (not as part of a brand name like "Make My Lemonade")
                # We look for tech signals in the immediate vicinity
                if not signal_pattern.search(stripped):
                    # Check broader context: look for tech signal within 200 chars of the match
                    m = combined.search(stripped)
                    if m:
                        start = max(0, m.start() - 100)
                        end = min(len(text), m.end() + 100)
                        context_window = text[start:end]
                        if not signal_pattern.search(context_window):
                            continue

            relevant.append(stripped)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for r in relevant:
            key = r[:60].lower()
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:4]

    def extract_search_context(self, text: str, query: str, title: str = "") -> list[str]:
        direct_context = self.extract_tool_context(text, query)
        if direct_context:
            return direct_context

        normalized_query = self._normalize_for_match(query)
        tokens = [token for token in re.split(r"\s+", normalized_query) if len(token) > 2]

        normalized_title = self._normalize_for_match(title)
        normalized_text = self._normalize_for_match(text)

        chunks = re.split(r"[\n•\-–—]|(?<=[.!?])\s+", text or "")
        if len(tokens) == 1:
            token = tokens[0] if tokens else ""
            if token and token in normalized_title and title:
                return [title.strip()]

            excerpts = []
            for chunk in chunks:
                stripped = chunk.strip()
                if len(stripped) < 25:
                    continue
                if token and token in self._normalize_for_match(stripped):
                    excerpts.append(stripped)
                if len(excerpts) >= 4:
                    break
            return excerpts[:4]

        if len(tokens) < 2:
            return []

        if normalized_query and (normalized_query in normalized_title or all(token in normalized_title for token in tokens)):
            return [title.strip()] if title else []

        excerpts = []
        minimum_hits = len(tokens) if len(tokens) <= 3 else len(tokens) - 1
        for chunk in chunks:
            stripped = chunk.strip()
            if len(stripped) < 25:
                continue
            normalized_chunk = self._normalize_for_match(stripped)
            if normalized_query and normalized_query in normalized_chunk:
                excerpts.append(stripped)
            else:
                chunk_hits = sum(token in normalized_chunk for token in tokens)
                if chunk_hits >= minimum_hits:
                    excerpts.append(stripped)
            if len(excerpts) >= 4:
                break

        if excerpts:
            return excerpts[:4]
        title_hits = sum(token in normalized_title for token in tokens)
        text_hits = sum(token in normalized_text for token in tokens)
        if title and title_hits >= minimum_hits and text_hits >= minimum_hits:
            return [title.strip()]
        return []

    def _normalize_for_match(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip().lower()

    def safe_get(self, url: str, **kwargs) -> requests.Response | None:
        try:
            resp = self.session.get(url, timeout=12, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            self.log.warning("GET %s failed: %s", url, e)
            return None

    def sleep(self):
        time.sleep(self.DELAY)


def parse_html(markup: str) -> BeautifulSoup:
    return BeautifulSoup(markup, HTML_PARSER)
