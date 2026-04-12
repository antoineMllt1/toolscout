import html
import json
import re
import unicodedata
import uuid

try:
    from normalization import build_normalized_result
except ModuleNotFoundError:
    from backend.normalization import build_normalized_result


CV_TEMPLATE_LIBRARY = [
    {
        "slug": "moderncv-classic",
        "family": "moderncv",
        "name": "ModernCV Classic",
        "style": "classic",
        "color": "green",
        "engine": "LaTeX",
        "backend_renderer": "moderncv",
        "supports_pdf": True,
        "description": "Base sobre pour candidatures generalistes, avec structure lisible et sections compactes.",
    },
    {
        "slug": "moderncv-banking",
        "family": "moderncv",
        "name": "ModernCV Banking",
        "style": "banking",
        "color": "red",
        "engine": "LaTeX",
        "backend_renderer": "moderncv",
        "supports_pdf": True,
        "description": "Version plus dense, utile pour profils data, finance et postes a forte composante analytique.",
    },
    {
        "slug": "moderncv-casual",
        "family": "moderncv",
        "name": "ModernCV Casual",
        "style": "casual",
        "color": "orange",
        "engine": "LaTeX",
        "backend_renderer": "moderncv",
        "supports_pdf": True,
        "description": "Variante plus editoriale, adaptee a un profil etudiant avec projets et portfolio.",
    },
]

TEMPLATE_BY_SLUG = {item["slug"]: item for item in CV_TEMPLATE_LIBRARY}

STRICT_COPY_RULES = [
    "Do not invent any employer, project, metric, certification, date, diploma, or technology.",
    "Only use facts present in the selected candidate profile entries and the job snapshot.",
    "Do not merge two different experiences into one bullet.",
    "Do not add quantified impact unless the user already provided the metric.",
    "Preserve names of companies, schools, technologies, and dates exactly.",
    "If information is missing, keep the wording simple instead of guessing.",
]

DEFAULT_CV_PROFILE = {
    "title": "Main profile",
    "full_name": "",
    "headline": "",
    "email": "",
    "phone": "",
    "location": "",
    "website": "",
    "linkedin": "",
    "github": "",
    "target_roles": [],
    "cv_text": "",
    "portfolio_url": "",
    "portfolio_snapshot": {},
    "portfolio_last_scraped_at": "",
    "summary": "",
    "skills": [],
    "languages": [],
    "certifications": [],
    "education": [],
    "experience": [],
    "projects": [],
}

STOPWORDS = {
    "and", "the", "for", "with", "that", "this", "from", "into", "your", "you",
    "des", "une", "pour", "avec", "dans", "sur", "les", "aux", "ses", "plus",
    "our", "nos", "notre", "their", "votre", "vos", "par", "est", "have", "has",
    "are", "been", "will", "ce", "cet", "cette", "qui", "quoi", "where", "when",
    "mission", "missions", "poste", "role", "roles", "job", "emploi", "offre",
    "work", "working", "candidate", "profil", "profile", "experience", "experiences",
    "projet", "project", "projects", "skills", "skill", "outils", "outil",
    "stage", "alternance", "internship", "apprenticeship", "junior", "senior",
    "entreprise", "company", "team", "equipe", "solution", "solutions",
}


def default_cv_profile(user: dict | None = None) -> dict:
    profile = dict(DEFAULT_CV_PROFILE)
    if user:
        profile["email"] = sanitize_line(user.get("email"))
        profile["full_name"] = sanitize_line(user.get("name"))
    return profile


def sanitize_line(value, max_length: int = 180) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length].strip()


def sanitize_block(value, max_length: int = 1200) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:max_length].strip()


def sanitize_string_list(values, max_items: int = 24, max_length: int = 120) -> list[str]:
    cleaned = []
    for value in values or []:
        text = sanitize_line(value, max_length=max_length)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _sanitize_date(value) -> str:
    return sanitize_line(value, max_length=40)


def _sanitize_entry_id(value) -> str:
    text = sanitize_line(value, max_length=40)
    return text or uuid.uuid4().hex[:10]


def sanitize_cv_profile(payload: dict, user: dict | None = None) -> dict:
    existing = default_cv_profile(user)
    base = payload or {}
    profile = {
        "title": sanitize_line(base.get("title") or existing["title"], 100) or "Main profile",
        "full_name": sanitize_line(base.get("full_name") or existing["full_name"], 120),
        "headline": sanitize_line(base.get("headline"), 140),
        "email": sanitize_line(base.get("email") or existing["email"], 140),
        "phone": sanitize_line(base.get("phone"), 60),
        "location": sanitize_line(base.get("location"), 120),
        "website": sanitize_line(base.get("website"), 180),
        "linkedin": sanitize_line(base.get("linkedin"), 180),
        "github": sanitize_line(base.get("github"), 180),
        "target_roles": sanitize_string_list(base.get("target_roles"), max_items=10, max_length=80),
        "cv_text": sanitize_block(base.get("cv_text"), 16000),
        "portfolio_url": sanitize_line(base.get("portfolio_url"), 220),
        "summary": sanitize_block(base.get("summary"), 900),
        "skills": sanitize_string_list(base.get("skills"), max_items=40, max_length=80),
        "languages": sanitize_string_list(base.get("languages"), max_items=16, max_length=80),
        "certifications": sanitize_string_list(base.get("certifications"), max_items=20, max_length=120),
        "education": _sanitize_education_entries(base.get("education")),
        "experience": _sanitize_experience_entries(base.get("experience")),
        "projects": _sanitize_project_entries(base.get("projects")),
    }
    return profile


def _sanitize_education_entries(entries) -> list[dict]:
    cleaned = []
    for raw in entries or []:
        item = {
            "id": _sanitize_entry_id(raw.get("id")),
            "school": sanitize_line(raw.get("school"), 120),
            "degree": sanitize_line(raw.get("degree"), 120),
            "field": sanitize_line(raw.get("field"), 120),
            "location": sanitize_line(raw.get("location"), 120),
            "start_date": _sanitize_date(raw.get("start_date")),
            "end_date": _sanitize_date(raw.get("end_date")),
            "summary": sanitize_block(raw.get("summary"), 700),
            "highlights": sanitize_string_list(raw.get("highlights"), max_items=6, max_length=180),
            "skills": sanitize_string_list(raw.get("skills"), max_items=12, max_length=80),
            "featured": bool(raw.get("featured", False)),
        }
        if item["school"] or item["degree"] or item["field"]:
            cleaned.append(item)
    return cleaned[:12]


def _sanitize_experience_entries(entries) -> list[dict]:
    cleaned = []
    for raw in entries or []:
        item = {
            "id": _sanitize_entry_id(raw.get("id")),
            "company": sanitize_line(raw.get("company"), 120),
            "title": sanitize_line(raw.get("title"), 140),
            "location": sanitize_line(raw.get("location"), 120),
            "start_date": _sanitize_date(raw.get("start_date")),
            "end_date": _sanitize_date(raw.get("end_date")),
            "summary": sanitize_block(raw.get("summary"), 800),
            "highlights": sanitize_string_list(raw.get("highlights"), max_items=8, max_length=180),
            "skills": sanitize_string_list(raw.get("skills"), max_items=14, max_length=80),
            "featured": bool(raw.get("featured", False)),
        }
        if item["company"] or item["title"]:
            cleaned.append(item)
    return cleaned[:20]


def _sanitize_project_entries(entries) -> list[dict]:
    cleaned = []
    for raw in entries or []:
        item = {
            "id": _sanitize_entry_id(raw.get("id")),
            "name": sanitize_line(raw.get("name"), 140),
            "role": sanitize_line(raw.get("role"), 120),
            "url": sanitize_line(raw.get("url"), 220),
            "summary": sanitize_block(raw.get("summary"), 800),
            "highlights": sanitize_string_list(raw.get("highlights"), max_items=8, max_length=180),
            "technologies": sanitize_string_list(raw.get("technologies"), max_items=14, max_length=80),
            "featured": bool(raw.get("featured", False)),
        }
        if item["name"] or item["role"]:
            cleaned.append(item)
    return cleaned[:20]


def _strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(char)
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\+\#\.]+", " ", _strip_accents((value or "").lower())).strip()


def _tokenize(value: str) -> list[str]:
    seen = []
    for token in _normalize_text(value).split():
        if len(token) < 2 or token in STOPWORDS or token.isdigit():
            continue
        if token not in seen:
            seen.append(token)
    return seen


def _dates_label(start_date: str, end_date: str) -> str:
    start = sanitize_line(start_date, 32)
    end = sanitize_line(end_date, 32)
    if start and end:
        return f"{start} - {end}"
    return start or end or "Dates a preciser"


def _entry_corpus(entry: dict, kind: str) -> str:
    if kind == "project":
        parts = [
            entry.get("name", ""),
            entry.get("role", ""),
            entry.get("summary", ""),
            " ".join(entry.get("highlights") or []),
            " ".join(entry.get("technologies") or []),
        ]
    elif kind == "education":
        parts = [
            entry.get("school", ""),
            entry.get("degree", ""),
            entry.get("field", ""),
            entry.get("summary", ""),
            " ".join(entry.get("highlights") or []),
            " ".join(entry.get("skills") or []),
        ]
    else:
        parts = [
            entry.get("company", ""),
            entry.get("title", ""),
            entry.get("summary", ""),
            " ".join(entry.get("highlights") or []),
            " ".join(entry.get("skills") or []),
        ]
    return " ".join(part for part in parts if part)


def _score_entry(entry: dict, kind: str, target_keywords: list[str]) -> dict:
    corpus = _entry_corpus(entry, kind)
    corpus_tokens = set(_tokenize(corpus))
    title_tokens = set(_tokenize(
        " ".join(
            [
                entry.get("title", ""),
                entry.get("company", ""),
                entry.get("name", ""),
                entry.get("role", ""),
                entry.get("school", ""),
                entry.get("degree", ""),
                entry.get("field", ""),
            ]
        )
    ))
    matched_terms = [keyword for keyword in target_keywords if keyword in corpus_tokens]
    title_hits = [keyword for keyword in target_keywords if keyword in title_tokens]
    score = len(matched_terms) * 3 + len(title_hits) * 2
    if entry.get("featured"):
        score += 2
    if not entry.get("end_date") or str(entry.get("end_date", "")).lower() in {"present", "current", "ongoing"}:
        score += 1
    if entry.get("summary"):
        score += 1
    return {
        "score": score,
        "matched_terms": matched_terms[:8],
        "entry": entry,
    }


def _pick_entries(entries: list[dict], kind: str, target_keywords: list[str], limit: int, fallback: int) -> list[dict]:
    scored = [_score_entry(entry, kind, target_keywords) for entry in entries]
    scored.sort(
        key=lambda item: (
            item["score"],
            item["entry"].get("featured", False),
            len(item["entry"].get("highlights") or []),
        ),
        reverse=True,
    )
    chosen = [item for item in scored if item["score"] > 0][:limit]
    if not chosen:
        chosen = scored[:fallback]
    payload = []
    for item in chosen:
        entry = dict(item["entry"])
        entry["matched_terms"] = item["matched_terms"]
        entry["match_score"] = item["score"]
        payload.append(entry)
    return payload


def build_target_snapshot(source_kind: str, record: dict) -> dict:
    normalized = record.get("normalized") or build_normalized_result(record)
    excerpts = sanitize_string_list(record.get("tool_context") or [], max_items=6, max_length=220)
    title = sanitize_line(record.get("job_title"), 180)
    company = sanitize_line(record.get("company_name"), 140)
    location = sanitize_line(record.get("location"), 140)
    contract = sanitize_line(record.get("contract_type"), 80) or normalized["contract"]["label"]
    focus_text = " ".join([title, company, location, contract, " ".join(excerpts)])
    keywords = _tokenize(focus_text)[:24]
    return {
        "source_kind": source_kind,
        "source_id": record.get("id"),
        "job_title": title,
        "company_name": company,
        "job_url": sanitize_line(record.get("job_url"), 240),
        "location": location,
        "contract_type": contract,
        "source": sanitize_line(record.get("source"), 50),
        "normalized": normalized,
        "excerpts": excerpts,
        "keywords": keywords,
    }


def _select_skills(skills: list[str], target_keywords: list[str], limit: int = 10) -> list[str]:
    matched = []
    remainder = []
    target_set = set(target_keywords)
    for skill in skills:
        tokens = set(_tokenize(skill))
        if tokens & target_set:
            matched.append(skill)
        else:
            remainder.append(skill)
    selected = matched[:limit]
    if len(selected) < limit:
        selected.extend(remainder[: limit - len(selected)])
    return selected


def build_targeted_cv_draft(profile: dict, target: dict, template_slug: str) -> dict:
    template = TEMPLATE_BY_SLUG.get(template_slug) or TEMPLATE_BY_SLUG["moderncv-classic"]
    target_keywords = target.get("keywords") or []

    selected_experience = _pick_entries(profile.get("experience") or [], "experience", target_keywords, limit=3, fallback=2)
    selected_projects = _pick_entries(profile.get("projects") or [], "project", target_keywords, limit=3, fallback=2)
    selected_education = _pick_entries(profile.get("education") or [], "education", target_keywords, limit=2, fallback=1)
    selected_skills = _select_skills(profile.get("skills") or [], target_keywords, limit=10)

    covered_terms = set()
    for entry in [*selected_experience, *selected_projects, *selected_education]:
        covered_terms.update(entry.get("matched_terms") or [])
    for skill in selected_skills:
        covered_terms.update(_tokenize(skill))

    missing_terms = [term for term in target_keywords if term not in covered_terms][:10]
    selected_payload = {
        "target": target,
        "skills": selected_skills,
        "languages": list(profile.get("languages") or []),
        "certifications": list(profile.get("certifications") or []),
        "experience": selected_experience,
        "projects": selected_projects,
        "education": selected_education,
        "match_summary": {
            "covered_terms": sorted(covered_terms)[:20],
            "missing_terms": missing_terms,
            "selected_counts": {
                "experience": len(selected_experience),
                "projects": len(selected_projects),
                "education": len(selected_education),
                "skills": len(selected_skills),
            },
        },
    }
    latex_source = render_moderncv_latex(profile, template, selected_payload)
    prompt_payload = build_copywriting_payload(profile, selected_payload, template)
    return {
        "template": template,
        "selected_payload": selected_payload,
        "latex_source": latex_source,
        "prompt_payload": prompt_payload,
    }


def build_copywriting_payload(profile: dict, selected_payload: dict, template: dict) -> dict:
    return {
        "template": {
            "family": template["family"],
            "style": template["style"],
            "color": template["color"],
        },
        "strict_rules": STRICT_COPY_RULES,
        "candidate_basics": {
            "full_name": profile.get("full_name", ""),
            "headline": profile.get("headline", ""),
            "summary": profile.get("summary", ""),
            "location": profile.get("location", ""),
        },
        "target": selected_payload["target"],
        "allowed_facts": {
            "skills": selected_payload["skills"],
            "languages": selected_payload["languages"],
            "certifications": selected_payload["certifications"],
            "experience": selected_payload["experience"],
            "projects": selected_payload["projects"],
            "education": selected_payload["education"],
        },
        "instructions": [
            "Rewrite only inside the selected facts.",
            "Keep the moderncv structure unchanged.",
            "Favor concise bullets aligned with the target role keywords.",
            "Do not output any fact that is absent from the allowed facts payload.",
        ],
    }


def _latex_escape(value: str) -> str:
    text = sanitize_block(value, max_length=4000)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _latex_handle(value: str) -> str:
    text = sanitize_line(value, 180)
    text = re.sub(r"^https?://(www\.)?", "", text)
    text = text.rstrip("/")
    text = text.replace("linkedin.com/in/", "")
    text = text.replace("github.com/", "")
    return text


def _latex_lines(values: list[str]) -> str:
    return r" \\ ".join(_latex_escape(value) for value in values if value)


def _latex_optional_command(command: str, value: str) -> list[str]:
    clean = sanitize_line(value, 220)
    if not clean:
        return []
    return [rf"\{command}{{{_latex_escape(clean)}}}"]


def _split_name(full_name: str) -> tuple[str, str]:
    parts = sanitize_line(full_name, 140).split()
    if not parts:
        return "Candidate", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def render_moderncv_latex(profile: dict, template: dict, selected_payload: dict) -> str:
    first_name, last_name = _split_name(profile.get("full_name") or "Candidate")
    headline = profile.get("headline") or selected_payload["target"].get("job_title") or "Targeted curriculum vitae"
    target = selected_payload["target"]
    lines = [
        r"\documentclass[11pt,a4paper,sans]{moderncv}",
        rf"\moderncvstyle{{{template['style']}}}",
        rf"\moderncvcolor{{{template['color']}}}",
        r"\usepackage[scale=0.86]{geometry}",
        "",
        rf"\name{{{_latex_escape(first_name)}}}{{{_latex_escape(last_name)}}}",
        rf"\title{{{_latex_escape(headline)}}}",
    ]
    lines.extend(_latex_optional_command("email", profile.get("email", "")))
    lines.extend(_latex_optional_command("phone[mobile]", profile.get("phone", "")))
    if profile.get("website"):
        website = sanitize_line(profile["website"], 180)
        lines.append(rf"\homepage{{{_latex_escape(website)}}}{{{_latex_escape(website)}}}")
    if profile.get("linkedin"):
        lines.append(rf"\social[linkedin]{{{_latex_escape(_latex_handle(profile['linkedin']))}}}")
    if profile.get("github"):
        lines.append(rf"\social[github]{{{_latex_escape(_latex_handle(profile['github']))}}}")

    lines.extend(
        [
            "",
            r"\begin{document}",
            r"\makecvtitle",
            "",
            r"\section{Target}",
            rf"\cvitem{{Role}}{{{_latex_escape(target.get('job_title') or 'Target role')}}}",
            rf"\cvitem{{Company}}{{{_latex_escape(target.get('company_name') or 'Company to confirm')}}}",
            rf"\cvitem{{Focus}}{{{_latex_escape(', '.join((target.get('keywords') or [])[:8]))}}}",
        ]
    )

    if profile.get("summary"):
        lines.extend(
            [
                "",
                r"\section{Profile}",
                rf"\cvitem{{}}{{{_latex_escape(profile['summary'])}}}",
            ]
        )
        if profile.get("location"):
            lines.append(rf"\cvitem{{Location}}{{{_latex_escape(profile['location'])}}}")
    elif profile.get("location"):
        lines.extend(
            [
                "",
                r"\section{Profile}",
                rf"\cvitem{{Location}}{{{_latex_escape(profile['location'])}}}",
            ]
        )

    if selected_payload["skills"]:
        lines.extend(
            [
                "",
                r"\section{Core Skills}",
                rf"\cvitem{{Tools}}{{{_latex_escape(', '.join(selected_payload['skills']))}}}",
            ]
        )

    if selected_payload["languages"]:
        lines.append(rf"\cvitem{{Languages}}{{{_latex_escape(', '.join(selected_payload['languages']))}}}")

    if selected_payload["certifications"]:
        lines.append(rf"\cvitem{{Certifications}}{{{_latex_escape(', '.join(selected_payload['certifications']))}}}")

    if selected_payload["experience"]:
        lines.append("")
        lines.append(r"\section{Experience}")
        for entry in selected_payload["experience"]:
            description_parts = []
            if entry.get("summary"):
                description_parts.append(entry["summary"])
            description_parts.extend(entry.get("highlights") or [])
            lines.append(
                rf"\cventry{{{_latex_escape(_dates_label(entry.get('start_date', ''), entry.get('end_date', '')))}}}"
                rf"{{{_latex_escape(entry.get('title') or 'Experience')}}}"
                rf"{{{_latex_escape(entry.get('company') or '')}}}"
                rf"{{{_latex_escape(entry.get('location') or '')}}}"
                r"{}"
                rf"{{{_latex_lines(description_parts)}}}"
            )

    if selected_payload["projects"]:
        lines.append("")
        lines.append(r"\section{Projects}")
        for entry in selected_payload["projects"]:
            description_parts = []
            if entry.get("summary"):
                description_parts.append(entry["summary"])
            if entry.get("technologies"):
                description_parts.append(f"Technologies: {', '.join(entry['technologies'])}")
            description_parts.extend(entry.get("highlights") or [])
            lines.append(
                rf"\cventry{{Project}}{{{_latex_escape(entry.get('name') or 'Project')}}}"
                rf"{{{_latex_escape(entry.get('role') or '')}}}"
                rf"{{{_latex_escape(entry.get('url') or '')}}}"
                r"{}"
                r"{}"
                rf"{{{_latex_lines(description_parts)}}}"
            )

    if selected_payload["education"]:
        lines.append("")
        lines.append(r"\section{Education}")
        for entry in selected_payload["education"]:
            title = " - ".join(filter(None, [entry.get("degree"), entry.get("field")]))
            description_parts = []
            if entry.get("summary"):
                description_parts.append(entry["summary"])
            description_parts.extend(entry.get("highlights") or [])
            lines.append(
                rf"\cventry{{{_latex_escape(_dates_label(entry.get('start_date', ''), entry.get('end_date', '')))}}}"
                rf"{{{_latex_escape(title or 'Education')}}}"
                rf"{{{_latex_escape(entry.get('school') or '')}}}"
                rf"{{{_latex_escape(entry.get('location') or '')}}}"
                r"{}"
                rf"{{{_latex_lines(description_parts)}}}"
            )

    lines.extend(["", r"\end{document}", ""])
    return "\n".join(lines)


def dumps_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)
