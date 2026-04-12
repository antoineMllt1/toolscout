from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from cv_engine import sanitize_block, sanitize_line, sanitize_string_list
except ModuleNotFoundError:
    from backend.cv_engine import sanitize_block, sanitize_line, sanitize_string_list

try:
    from portfolio_ingest import ROLE_PLAYBOOKS, _normalize_text, _match_playbooks
except ModuleNotFoundError:
    from backend.portfolio_ingest import ROLE_PLAYBOOKS, _normalize_text, _match_playbooks

try:
    from scrapers.base import parse_html
except ModuleNotFoundError:
    from backend.scrapers.base import parse_html


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT_SECONDS = 18

TRACKER_STATUS_META = [
    {"key": "saved", "label": "A qualifier", "description": "Opportunites sauvegardees a relire ou a scorer."},
    {"key": "applied", "label": "Postule", "description": "Candidatures envoyees."},
    {"key": "interview", "label": "Entretien", "description": "Entretiens ou cas en cours."},
    {"key": "offer", "label": "Offre", "description": "Issue positive ou proposition."},
    {"key": "rejected", "label": "Refus", "description": "Issue negative ou cloture externe."},
]

STATUS_LABEL_MAP = {item["key"]: item["label"] for item in TRACKER_STATUS_META}

TRAINING_LOW_SIGNAL = [
    "bootcamp",
    "intro",
    "beginner",
    "masterclass",
    "certificate of completion",
    "linkedin learning",
]


def tracker_status_meta() -> list[dict]:
    return TRACKER_STATUS_META


def tracker_status_label(status: str) -> str:
    return STATUS_LABEL_MAP.get((status or "").strip(), status or "Unknown")


def story_bank_suggestions(profile: dict) -> list[dict]:
    suggestions = []
    for item in profile.get("experience") or []:
        title = " - ".join(part for part in [item.get("title"), item.get("company")] if part).strip()
        if not title:
            continue
        suggestions.append(
            {
                "title": title,
                "kind": "experience",
                "situation": item.get("summary") or "",
                "task": "Quel etait l'objectif ou la responsabilite principale ?",
                "action": (item.get("highlights") or ["Decris les actions que tu as vraiment portees."])[0],
                "result": "",
                "reflection": "Qu'as-tu appris et que referais-tu differemment ?",
                "tags": sanitize_string_list([*(item.get("skills") or []), item.get("company", "")], max_items=4, max_length=50),
            }
        )
    for item in profile.get("projects") or []:
        title = item.get("name") or item.get("role") or ""
        if not title:
            continue
        suggestions.append(
            {
                "title": title,
                "kind": "project",
                "situation": item.get("summary") or "",
                "task": "Quel probleme voulais-tu resoudre ?",
                "action": (item.get("highlights") or ["Decris les choix techniques et produit que tu as faits."])[0],
                "result": "",
                "reflection": "Qu'est-ce que ce projet prouve pour un recruteur ?",
                "tags": sanitize_string_list([*(item.get("technologies") or []), "project"], max_items=4, max_length=50),
            }
        )
    return suggestions[:8]


def _fetch_html(url: str) -> tuple[str, BeautifulSoup]:
    normalized_url = sanitize_line(url, 240)
    if normalized_url and not normalized_url.startswith(("http://", "https://")):
        normalized_url = f"https://{normalized_url}"
    response = requests.get(normalized_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.url, parse_html(response.text)


def scan_company_portal(company_name: str, careers_url: str) -> dict:
    final_url, soup = _fetch_html(careers_url)
    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(final_url, anchor.get("href", ""))
        label = sanitize_line(anchor.get_text(" ", strip=True), 140)
        haystack = _normalize_text(" ".join([href, label]))
        if not any(term in haystack for term in ["job", "career", "opening", "intern", "stage", "alternance", "position", "role"]):
            continue
        key = (href.lower(), label.lower())
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "title": label or href,
                "url": href,
                "host": urlparse(href).netloc.replace("www.", ""),
            }
        )
        if len(links) >= 20:
            break

    page_text = sanitize_block((soup.body or soup).get_text(" ", strip=True), 4000)
    internship_signals = []
    if "intern" in _normalize_text(page_text) or "stage" in _normalize_text(page_text):
        internship_signals.append("The page mentions internships or stage opportunities.")
    if "remote" in _normalize_text(page_text):
        internship_signals.append("Remote or hybrid work is mentioned.")
    if "graduate" in _normalize_text(page_text) or "student" in _normalize_text(page_text):
        internship_signals.append("Student or graduate language appears on the page.")

    return {
        "company_name": sanitize_line(company_name, 120),
        "careers_url": final_url,
        "jobs_found": links,
        "summary": f"{len(links)} potentially useful career links found for {company_name}.",
        "signals": internship_signals[:5],
        "scanned_at": datetime.utcnow().isoformat(),
    }


def _portal_job_key(job: dict) -> str:
    url = sanitize_line(job.get("url"), 320).lower().rstrip("/")
    title = sanitize_line(job.get("title"), 160).lower()
    return url or title


def diff_company_portal_results(previous_result: dict | None, current_result: dict | None) -> dict:
    previous_jobs = (previous_result or {}).get("jobs_found") or []
    current_jobs = (current_result or {}).get("jobs_found") or []

    previous_index = {}
    for job in previous_jobs:
        key = _portal_job_key(job)
        if key:
            previous_index[key] = job

    current_index = {}
    for job in current_jobs:
        key = _portal_job_key(job)
        if key:
            current_index[key] = job

    new_jobs = [job for key, job in current_index.items() if key not in previous_index]
    removed_jobs = [job for key, job in previous_index.items() if key not in current_index]
    changed = bool(new_jobs or removed_jobs)

    if not previous_jobs:
        summary = f"Baseline created with {len(current_jobs)} visible job links."
    elif not changed:
        summary = "No visible change since the previous company scan."
    else:
        bits = []
        if new_jobs:
            bits.append(f"{len(new_jobs)} new")
        if removed_jobs:
            bits.append(f"{len(removed_jobs)} removed")
        summary = ", ".join(bits) + "."

    return {
        "changed": changed,
        "summary": summary,
        "jobs_found_count": len(current_jobs),
        "previous_jobs_count": len(previous_jobs),
        "new_jobs_count": len(new_jobs),
        "removed_jobs_count": len(removed_jobs),
        "new_jobs": new_jobs[:8],
        "removed_jobs": removed_jobs[:8],
        "signals": (current_result or {}).get("signals") or [],
        "scanned_at": (current_result or {}).get("scanned_at"),
    }


def build_company_research(company_name: str, source_url: str, role_title: str = "") -> dict:
    final_url, soup = _fetch_html(source_url)
    title = sanitize_line(soup.title.get_text(" ", strip=True) if soup.title else company_name, 160)
    headings = []
    for node in soup.find_all(["h1", "h2", "h3"], limit=12):
        text = sanitize_line(node.get_text(" ", strip=True), 120)
        if text and text not in headings:
            headings.append(text)
    paragraphs = []
    for node in soup.find_all("p", limit=12):
        text = sanitize_block(node.get_text(" ", strip=True), 220)
        if len(text) >= 48 and text not in paragraphs:
            paragraphs.append(text)

    corpus = " ".join([title, " ".join(headings), " ".join(paragraphs)])
    normalized = _normalize_text(corpus)

    product_signals = []
    culture_signals = []
    risks = []

    for token, message in [
        ("ai", "AI appears to be central in the positioning or product vocabulary."),
        ("platform", "The company presents itself as a platform product."),
        ("enterprise", "Enterprise language appears in the public copy."),
        ("developer", "Developer-facing signals appear in the site copy."),
        ("data", "Data or analytics appear in the company narrative."),
        ("automation", "Automation is part of the company positioning."),
    ]:
        if token in normalized:
            product_signals.append(message)

    for token, message in [
        ("remote", "Remote or distributed work is referenced."),
        ("ownership", "Ownership language appears in the site copy."),
        ("fast", "The tone suggests speed, pace or rapid execution."),
        ("collaboration", "Collaboration is explicitly mentioned."),
        ("learning", "Learning or growth language appears."),
        ("intern", "Student or intern language appears."),
    ]:
        if token in normalized:
            culture_signals.append(message)

    if len(paragraphs) < 2:
        risks.append("The public site gives limited context, so interview prep will need external research.")
    if "intern" not in normalized and "student" not in normalized and role_title:
        risks.append("No student-specific signal detected on the source page.")
    if not product_signals:
        risks.append("Product positioning is still fuzzy from the provided source URL.")

    summary_bits = [paragraphs[0] if paragraphs else "", paragraphs[1] if len(paragraphs) > 1 else ""]
    summary = sanitize_block(" ".join(bit for bit in summary_bits if bit), 500) or f"Research snapshot for {company_name}."

    return {
        "company_name": sanitize_line(company_name, 120),
        "role_title": sanitize_line(role_title, 120),
        "source_url": final_url,
        "page_title": title,
        "summary": summary,
        "headings": headings[:6],
        "product_signals": product_signals[:6],
        "culture_signals": culture_signals[:6],
        "risks": risks[:6],
        "research_date": datetime.utcnow().isoformat(),
    }


def evaluate_training_fit(profile: dict, topic: str) -> dict:
    playbooks = _match_playbooks(profile)
    topic_text = sanitize_line(topic, 180)
    normalized_topic = _normalize_text(topic_text)
    known_skills = set(_normalize_text(skill) for skill in (profile.get("skills") or []))

    role_match = 0
    for playbook in playbooks:
        if any(keyword in normalized_topic for keyword in playbook["keywords"]):
            role_match += 1

    already_covered = any(skill and skill in normalized_topic for skill in known_skills)
    low_signal = any(term in normalized_topic for term in TRAINING_LOW_SIGNAL)
    score = 2 + role_match * 2 + (0 if low_signal else 1) - (1 if already_covered else 0)

    if score >= 5:
        verdict = "High ROI"
    elif score >= 3:
        verdict = "Medium ROI"
    else:
        verdict = "Low ROI"

    reasons = []
    if role_match:
        reasons.append("The topic aligns with your target roles.")
    if already_covered:
        reasons.append("This area already appears in your current skills, so the signaling gain may be limited.")
    else:
        reasons.append("This topic could help close an obvious signal gap in your profile.")
    if low_signal:
        reasons.append("The format sounds generic, so the credential itself may not move the needle much.")
    else:
        reasons.append("If you finish it with a concrete portfolio output, the signal becomes stronger.")

    next_steps = [
        "Only do it if you can turn it into one visible project, case study or GitHub artifact.",
        "Mention the training only after the resulting deliverable is credible enough to show.",
        "Prefer short, role-specific training over broad generic programs.",
    ]

    return {
        "kind": "training",
        "topic": topic_text,
        "verdict": verdict,
        "score": max(1, min(score, 5)),
        "reasons": reasons[:4],
        "next_steps": next_steps,
        "role_tracks": [playbook["label"] for playbook in playbooks],
    }


def evaluate_project_fit(profile: dict, idea: str) -> dict:
    playbooks = _match_playbooks(profile)
    idea_text = sanitize_block(idea, 600)
    normalized_idea = _normalize_text(idea_text)
    existing_projects = profile.get("projects") or []

    role_match = 0
    for playbook in playbooks:
        if any(keyword in normalized_idea for keyword in playbook["keywords"]):
            role_match += 1

    differentiation = 4 if not any(_normalize_text(project.get("name", "")) in normalized_idea for project in existing_projects) else 2
    scope = 4 if any(term in normalized_idea for term in ["dashboard", "assistant", "api", "workflow", "prototype", "audit"]) else 3
    score = min(5, max(1, role_match + differentiation // 2 + scope // 2))

    deliverables = [
        "A live demo or short video walkthrough.",
        "A concise README with problem, approach, stack and results.",
        "One screenshot or artifact that makes the project legible in 10 seconds.",
    ]
    proof_points = [
        "Explain what problem the project solves.",
        "Show one concrete decision you had to make.",
        "Make the output inspectable by a recruiter.",
    ]

    if score >= 5:
        verdict = "Strong project"
    elif score >= 3:
        verdict = "Promising but sharpen it"
    else:
        verdict = "Weak signal as described"

    return {
        "kind": "project",
        "idea": idea_text,
        "verdict": verdict,
        "score": score,
        "role_tracks": [playbook["label"] for playbook in playbooks],
        "deliverables": deliverables,
        "proof_points": proof_points,
        "positioning": [
            "Frame it around a real user, team or business problem.",
            "Keep the scope narrow enough to finish and present cleanly.",
            "Prefer one polished project over three vague experiments.",
        ],
    }
