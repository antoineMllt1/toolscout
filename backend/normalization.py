import re
import unicodedata


SOURCE_LABELS = {
    "wttj": "Welcome to the Jungle",
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "jobteaser": "JobTeaser",
    "hellowork": "HelloWork",
}

CONTRACT_RULES = [
    ("internship", "Stage", (r"\bstage\b",)),
    ("apprenticeship", "Alternance", (r"\balternance\b", r"\bapprentissage\b")),
    ("freelance", "Freelance", (r"\bfreelance\b", r"\bcontractor\b", r"\bmission\b")),
    ("temporary", "CDD", (r"\bcdd\b", r"\btemporaire\b", r"\bcontract\b")),
    ("permanent", "CDI", (r"\bcdi\b", r"\bpermanent\b")),
    ("part_time", "Temps partiel", (r"\btemps partiel\b", r"\bpart[- ]time\b")),
    ("full_time", "Temps plein", (r"\btemps plein\b", r"\bfull[- ]time\b")),
]

REMOTE_RULES = [
    ("remote", "Remote", (r"\bremote\b", r"\bt[ée]l[ée]travail\b", r"\b100 ?% remote\b", r"\bfull remote\b")),
    ("hybrid", "Hybride", (r"\bhybrid\b", r"\bhybride\b", r"\b2 jours\b", r"\b3 jours\b")),
    ("onsite", "Sur site", (r"\bon[- ]site\b", r"\bpr[ée]sentiel\b")),
]

SENIORITY_RULES = [
    ("intern", "Stage/Junior", (r"\bstagiaire\b", r"\bintern(ship)?\b", r"\balternan", r"\bjunior\b")),
    ("mid", "Confirmé", (r"\bconfirm[ée]\b", r"\bmid\b", r"\binterm[ée]diaire\b")),
    ("senior", "Senior", (r"\bsenior\b", r"\blead\b", r"\bprincipal\b", r"\bstaff\b", r"\bexpert\b")),
]


def _strip_accents(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(char)
    )


def slugify(value: str) -> str:
    stripped = _strip_accents((value or "").lower())
    return re.sub(r"[^a-z0-9]+", "-", stripped).strip("-")


def normalize_source(source: str) -> dict:
    key = slugify(source).replace("-", "")
    canonical = {
        "welcometothejungle": "wttj",
        "jobteaser": "jobteaser",
        "linkedin": "linkedin",
        "indeed": "indeed",
        "hellowork": "hellowork",
        "wttj": "wttj",
    }.get(key, source or "unknown")
    return {"key": canonical, "label": SOURCE_LABELS.get(canonical, source or "Unknown")}


def normalize_contract(contract_type: str) -> dict:
    raw = (contract_type or "").strip()
    haystack = _strip_accents(raw.lower())
    for key, label, patterns in CONTRACT_RULES:
        if any(re.search(pattern, haystack) for pattern in patterns):
            return {"key": key, "label": label}
    if not raw:
        return {"key": "unknown", "label": "Non précisé"}
    return {"key": slugify(raw), "label": raw}


def normalize_remote_mode(location: str, job_title: str, context: list[str] | str) -> dict:
    snippets = context if isinstance(context, list) else [context]
    haystack = " ".join(filter(None, [location, job_title, *snippets]))
    haystack = _strip_accents(haystack.lower())
    for key, label, patterns in REMOTE_RULES:
        if any(re.search(pattern, haystack) for pattern in patterns):
            return {"key": key, "label": label}
    return {"key": "unknown", "label": "À vérifier"}


def normalize_seniority(job_title: str, context: list[str] | str) -> dict:
    snippets = context if isinstance(context, list) else [context]
    haystack = " ".join(filter(None, [job_title, *snippets]))
    haystack = _strip_accents(haystack.lower())
    for key, label, patterns in SENIORITY_RULES:
        if any(re.search(pattern, haystack) for pattern in patterns):
            return {"key": key, "label": label}
    return {"key": "unknown", "label": "Non précisé"}


def normalize_location(location: str) -> dict:
    raw = (location or "").strip()
    compact = re.sub(r"\s+", " ", raw)
    if not compact:
        return {"city": "", "label": "Lieu non précisé"}
    parts = [part.strip() for part in re.split(r"[,/|-]", compact) if part.strip()]
    return {"city": parts[0] if parts else compact, "label": compact}


def match_role_targets(job_title: str, role_targets: list[str]) -> list[str]:
    title = _strip_accents((job_title or "").lower())
    matches = []
    for target in role_targets:
        normalized = _strip_accents((target or "").lower()).strip()
        if not normalized:
            continue
        tokens = [token for token in re.split(r"\s+", normalized) if len(token) > 2]
        if normalized in title or all(token in title for token in tokens):
            matches.append(target)
    return matches


def build_normalized_result(result: dict) -> dict:
    context = result.get("tool_context") or []
    return {
        "source": normalize_source(result.get("source", "")),
        "contract": normalize_contract(result.get("contract_type", "")),
        "location": normalize_location(result.get("location", "")),
        "remote_mode": normalize_remote_mode(result.get("location", ""), result.get("job_title", ""), context),
        "seniority": normalize_seniority(result.get("job_title", ""), context),
    }
