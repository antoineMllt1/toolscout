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
    ("remote", "Remote", (r"\bremote\b", r"\bteletravail\b", r"\b100 ?% remote\b", r"\bfull remote\b")),
    ("hybrid", "Hybride", (r"\bhybrid\b", r"\bhybride\b", r"\b2 jours\b", r"\b3 jours\b")),
    ("onsite", "Sur site", (r"\bon[- ]site\b", r"\bpresentiel\b")),
]

SENIORITY_RULES = [
    ("intern", "Stage/Junior", (r"\bstagiaire\b", r"\bintern(ship)?\b", r"\balternan", r"\bjunior\b")),
    ("mid", "Confirme", (r"\bconfirme\b", r"\bmid\b", r"\bintermediaire\b")),
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
        return {"key": "unknown", "label": "Non precise"}
    return {"key": slugify(raw), "label": raw}


def normalize_remote_mode(location: str, job_title: str, context: list[str] | str) -> dict:
    snippets = context if isinstance(context, list) else [context]
    haystack = " ".join(filter(None, [location, job_title, *snippets]))
    haystack = _strip_accents(haystack.lower())
    for key, label, patterns in REMOTE_RULES:
        if any(re.search(pattern, haystack) for pattern in patterns):
            return {"key": key, "label": label}
    return {"key": "unknown", "label": "A verifier"}


def normalize_seniority(job_title: str, context: list[str] | str) -> dict:
    snippets = context if isinstance(context, list) else [context]
    haystack = " ".join(filter(None, [job_title, *snippets]))
    haystack = _strip_accents(haystack.lower())
    for key, label, patterns in SENIORITY_RULES:
        if any(re.search(pattern, haystack) for pattern in patterns):
            return {"key": key, "label": label}
    return {"key": "unknown", "label": "Non precise"}


def _normalize_city_label(value: str) -> str:
    clean = (value or "").strip()
    clean = re.sub(r"\b\d{5}\b", "", clean)
    clean = re.sub(r"\((?:75|77|78|91|92|93|94|95)\)", "", clean)
    clean = re.sub(
        r"\b(paris|lyon|marseille)\s+(?:\d{1,2}(?:er|e|eme)?|[ivxlcdm]+(?:e|er)?)\b",
        r"\1",
        clean,
        flags=re.I,
    )
    clean = re.sub(r"\s+", " ", clean).strip(" ,;-")
    return clean.title()


def normalize_location(location: str) -> dict:
    raw = (location or "").strip()
    compact = re.sub(r"\s+", " ", raw)
    if not compact:
        return {"city": "", "city_key": "", "label": "Lieu non precise", "parts": []}
    parts = [part.strip() for part in re.split(r"\s+-\s+|[,/|]", compact) if part.strip()]
    primary = parts[0] if parts else compact
    city = _normalize_city_label(primary)
    return {
        "city": city,
        "city_key": slugify(city),
        "label": compact,
        "parts": parts[:4],
    }


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


def summarize_role_snippets(
    *,
    job_title: str,
    company_name: str,
    location_label: str,
    contract_label: str,
    snippets: list[str] | str,
) -> str:
    snippet_items = snippets if isinstance(snippets, list) else [snippets]
    clean_snippets = [snippet.strip() for snippet in snippet_items if isinstance(snippet, str) and snippet.strip()]

    opener_bits = [job_title.strip()]
    if company_name:
        opener_bits.append(f"chez {company_name.strip()}")
    if location_label:
        opener_bits.append(f"a {location_label.strip()}")
    if contract_label and contract_label != "Non precise":
        opener_bits.append(f"en {contract_label.strip()}")

    opener = " ".join(bit for bit in opener_bits if bit).strip()
    if clean_snippets:
        body = re.sub(r"\s+", " ", " ".join(clean_snippets[:2])).strip()
        return f"{opener}. {body}" if opener else body
    return opener or "Resume de poste indisponible."


def build_normalized_result(result: dict) -> dict:
    context = result.get("tool_context") or []
    location = normalize_location(result.get("location", ""))
    contract = normalize_contract(result.get("contract_type", ""))
    return {
        "source": normalize_source(result.get("source", "")),
        "contract": contract,
        "location": location,
        "remote_mode": normalize_remote_mode(result.get("location", ""), result.get("job_title", ""), context),
        "seniority": normalize_seniority(result.get("job_title", ""), context),
        "role_summary": summarize_role_snippets(
            job_title=result.get("job_title", ""),
            company_name=result.get("company_name", ""),
            location_label=location.get("label", ""),
            contract_label=contract.get("label", ""),
            snippets=context,
        ),
        "summary_highlights": [snippet.strip() for snippet in context[:3] if isinstance(snippet, str) and snippet.strip()],
    }
