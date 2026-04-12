import json
import logging
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from cv_engine import sanitize_block, sanitize_cv_profile, sanitize_line, sanitize_string_list
except ModuleNotFoundError:
    from backend.cv_engine import sanitize_block, sanitize_cv_profile, sanitize_line, sanitize_string_list

try:
    from anthropic_client import extract_portfolio_snapshot
except ModuleNotFoundError:
    from backend.anthropic_client import extract_portfolio_snapshot

try:
    from scrapers.base import parse_html
except ModuleNotFoundError:
    from backend.scrapers.base import parse_html

logger = logging.getLogger("toolscout.portfolio")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT_SECONDS = 18
PORTFOLIO_PAGE_LIMIT = max(1, min(6, int(os.environ.get("PORTFOLIO_PAGE_LIMIT", "4"))))
PORTFOLIO_PAGE_TEXT_LIMIT = max(1200, min(8000, int(os.environ.get("PORTFOLIO_PAGE_TEXT_LIMIT", "4500"))))
PORTFOLIO_LINK_HINTS = (
    "project",
    "projects",
    "work",
    "case",
    "study",
    "portfolio",
    "about",
    "experience",
    "resume",
    "cv",
)
PORTFOLIO_LINK_SKIP_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".mp4",
    ".webm",
)
GITHUB_PROJECT_FILE_CANDIDATES = [
    "src/data/projects.js",
    "src/data/projects.ts",
    "src/data/projects.jsx",
    "src/data/projects.tsx",
    "src/projects.js",
    "src/projects.ts",
    "data/projects.js",
    "data/projects.ts",
    "projects.js",
    "projects.ts",
]
GITHUB_ROLE_LABELS = {
    "data": "Data Analyst",
    "automation": "Consultant IA & Automation",
    "ai": "AI / Automation",
    "product": "Product",
    "frontend": "Frontend",
    "backend": "Backend",
}
COMMON_TECH = [
    "Python",
    "SQL",
    "JavaScript",
    "TypeScript",
    "React",
    "Next.js",
    "Node.js",
    "FastAPI",
    "Django",
    "Flask",
    "Tailwind",
    "HTML",
    "CSS",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "SQLite",
    "Pandas",
    "NumPy",
    "scikit-learn",
    "TensorFlow",
    "PyTorch",
    "OpenAI",
    "Claude",
    "LangChain",
    "Docker",
    "Git",
    "GitHub",
    "Vercel",
    "AWS",
    "Azure",
    "GCP",
    "Power BI",
    "Tableau",
    "dbt",
    "Looker",
    "Figma",
    "Notion",
    "Airtable",
    "HubSpot",
    "Make",
    "n8n",
    "Zapier",
    "Java",
    "C",
    "C++",
    "C#",
    "Go",
    "Rust",
    "PHP",
    "Laravel",
    "Vue",
    "Nuxt",
    "Svelte",
    "Firebase",
    "Supabase",
    "Redis",
    "GraphQL",
    "REST API",
    "Machine Learning",
    "Deep Learning",
    "Data Analysis",
    "Analytics",
    "Product Management",
]

ROLE_PLAYBOOKS = [
    {
        "slug": "data",
        "label": "Data / BI",
        "keywords": ["data", "analyst", "analytics", "bi", "business intelligence", "tableau", "power bi", "sql"],
        "ideas": [
            {
                "title": "Dashboard de pilotage pour une startup fictive",
                "brief": "Construis une mini stack analytique avec donnees brutes, modele propre et dashboard de decision.",
                "stack": ["SQL", "dbt", "Python", "Power BI"],
                "why_it_helps": "Montre a la fois la rigueur data, la visualisation et la capacite a parler business.",
            },
            {
                "title": "Audit produit d'une app publique",
                "brief": "Collecte des donnees publiques, cree des KPI et formule 3 recommandations produit chiffrables.",
                "stack": ["Python", "SQL", "Pandas", "Notion"],
                "why_it_helps": "Tres bon format pour un stage data ou product analytics.",
            },
        ],
    },
    {
        "slug": "ai",
        "label": "AI / ML",
        "keywords": ["ai", "ml", "machine learning", "llm", "data science", "nlp", "pytorch", "tensorflow"],
        "ideas": [
            {
                "title": "Assistant IA specialise pour etudiants",
                "brief": "Construit un assistant vertical avec retrieval, garde-fous simples et mesure qualitative des reponses.",
                "stack": ["Python", "FastAPI", "OpenAI", "Vector DB"],
                "why_it_helps": "Projet lisible, concret, deployable et facile a raconter en entretien.",
            },
            {
                "title": "Benchmark de prompts et workflows LLM",
                "brief": "Compare plusieurs prompts ou pipelines sur un petit jeu d'evaluation et publie les resultats.",
                "stack": ["Python", "Jupyter", "OpenAI", "Pandas"],
                "why_it_helps": "Prouve une approche experimentale plutot qu'un simple demo prompt.",
            },
        ],
    },
    {
        "slug": "frontend",
        "label": "Frontend",
        "keywords": ["frontend", "front-end", "react", "ui", "ux", "web"],
        "ideas": [
            {
                "title": "Refonte complete d'un dashboard orientee usage",
                "brief": "Prends un dashboard existant, revois l'architecture des ecrans et documente les choix UI.",
                "stack": ["React", "CSS", "Figma", "Vite"],
                "why_it_helps": "Tres utile pour montrer intention produit et execution visuelle.",
            },
            {
                "title": "Design system minimal pour produit SaaS",
                "brief": "Cree tokens, composants, et exemples d'ecrans coherents avec documentation concise.",
                "stack": ["React", "Storybook", "CSS", "Accessibility"],
                "why_it_helps": "Prouve ton niveau de structure, pas seulement de pixel pushing.",
            },
        ],
    },
    {
        "slug": "backend",
        "label": "Backend / API",
        "keywords": ["backend", "back-end", "api", "python", "fastapi", "node", "server"],
        "ideas": [
            {
                "title": "API de candidatures avec scoring et historique",
                "brief": "Cree une API propre avec auth, persistence, jobs asynchrones et logs utiles.",
                "stack": ["Python", "FastAPI", "SQLite", "Docker"],
                "why_it_helps": "Bon miroir des attentes stage backend: CRUD solide, auth et jobs.",
            },
            {
                "title": "Moteur de scraping robuste sur 2-3 sources",
                "brief": "Normalise les donnees, gere les erreurs et expose un endpoint de supervision.",
                "stack": ["Python", "Playwright", "FastAPI", "SQLite"],
                "why_it_helps": "Montre rigueur technique, resilience et gestion du reel.",
            },
        ],
    },
    {
        "slug": "product",
        "label": "Product / PM",
        "keywords": ["product", "pm", "product manager", "growth", "strategy"],
        "ideas": [
            {
                "title": "Memo produit + prototype + plan de mesure",
                "brief": "Choisis une douleur utilisateur concrete, propose une solution et definis comment la mesurer.",
                "stack": ["Figma", "Notion", "Analytics", "User research"],
                "why_it_helps": "Le trio probleme, priorisation, metriques parle beaucoup aux recruteurs produit.",
            },
            {
                "title": "Reverse engineering d'une fonctionnalite SaaS",
                "brief": "Analyse un produit connu, reconstruis la logique et propose un plan d'amelioration priorise.",
                "stack": ["Notion", "Slides", "Figma"],
                "why_it_helps": "Simple a produire, fort pour montrer ta pensee produit.",
            },
        ],
    },
    {
        "slug": "ops",
        "label": "Ops / Automation",
        "keywords": ["ops", "automation", "no-code", "make", "zapier", "n8n", "revops"],
        "ideas": [
            {
                "title": "Pipeline d'automatisation pour une asso etudiante",
                "brief": "Automatise leads, relances, reporting et passage de statuts entre plusieurs outils.",
                "stack": ["n8n", "Airtable", "Notion", "Slack"],
                "why_it_helps": "Projet concret, tres lisible et directement actionnable en entretien.",
            },
            {
                "title": "Cockpit operationnel avec alertes et KPI",
                "brief": "Monte une vue de supervision pour une mini equipe avec SLA, backlog et automatisations.",
                "stack": ["Airtable", "Make", "Looker Studio"],
                "why_it_helps": "Montre structure, sens du process et execution orientee business.",
            },
        ],
    },
]

MOTIVATION_QUESTIONS = [
    {
        "category": "Motivation",
        "question": "Pourquoi ce role est cohérent avec ton parcours actuel ?",
        "why_asked": "Valider que ta candidature est intentionnelle et pas opportuniste.",
        "answer_shape": "Lien entre ton parcours, ce que tu sais deja faire, et ce que tu veux apprendre ensuite.",
    },
    {
        "category": "Motivation",
        "question": "Pourquoi ce type d'entreprise ou d'equipe t'interesse pour ton stage ?",
        "why_asked": "Tester ton niveau de projection dans un environnement concret.",
        "answer_shape": "1 contexte prefere, 1 raison d'apprentissage, 1 type d'impact recherche.",
    },
]

TECHNICAL_QUESTION_BANK = {
    "data": [
        {
            "question": "Comment verifierais-tu qu'un dashboard raconte la bonne histoire business ?",
            "why_asked": "Verifier ton sens analytique et ta rigueur sur la qualite des KPI.",
            "answer_shape": "Definir l'objectif, verifier les sources, controler les calculs, tester avec un cas reel.",
        },
        {
            "question": "Raconte une analyse ou tu as du transformer des donnees brutes en decision utile.",
            "why_asked": "Voir si tu sais aller au-dela du reporting descriptif.",
            "answer_shape": "Probleme, nettoyage, analyse, insight, recommandation.",
        },
    ],
    "ai": [
        {
            "question": "Comment evaluerais-tu rapidement un prototype IA avant de le montrer a un recruteur ?",
            "why_asked": "Tester si tu raisonnes en qualite, garde-fous et limites.",
            "answer_shape": "Cas d'usage, exemples de test, limites connues, ameliorations prevues.",
        },
        {
            "question": "Parle-moi d'un systeme IA ou d'un workflow LLM que tu as construit ou etudie.",
            "why_asked": "Verifier que tu comprends la chaine de valeur d'un projet IA.",
            "answer_shape": "Objectif, architecture simple, choix techniques, limites observees.",
        },
    ],
    "frontend": [
        {
            "question": "Comment decides-tu qu'une interface est vraiment plus claire apres une refonte ?",
            "why_asked": "Chercher une pensee UI reliee a l'usage plutot qu'au style.",
            "answer_shape": "Hypothese, simplification, cas d'usage, retour utilisateur ou auto-critique.",
        },
        {
            "question": "Raconte un compromis que tu as fait entre rapidite de livraison et qualite front.",
            "why_asked": "Verifier ton jugement produit et technique.",
            "answer_shape": "Contrainte, options, choix, resultat, dette restante.",
        },
    ],
    "backend": [
        {
            "question": "Comment rendrais-tu une petite API plus fiable sans la complexifier inutilement ?",
            "why_asked": "Mesurer ta maturite sur la robustesse et les priorites backend.",
            "answer_shape": "Validation, logs, gestion d'erreurs, structure des reponses, tests ciblés.",
        },
        {
            "question": "Parle-moi d'un bug ou d'une source d'instabilite que tu as du isoler.",
            "why_asked": "Evaluer ton raisonnement de debugging.",
            "answer_shape": "Symptome, hypothese, test, correction, prevention.",
        },
    ],
    "product": [
        {
            "question": "Comment prioriserais-tu 3 idees si tu n'as presque pas de donnees ?",
            "why_asked": "Tester ton jugement produit en contexte imparfait.",
            "answer_shape": "Impact potentiel, effort, risque, apprentissage rapide.",
        },
        {
            "question": "Raconte une situation ou tu as clarifie un besoin flou.",
            "why_asked": "Chercher ton niveau de structuration et d'alignement.",
            "answer_shape": "Contexte flou, cadrage, reformulation, decision prise.",
        },
    ],
    "ops": [
        {
            "question": "Comment identifies-tu ce qu'il faut automatiser en premier dans un process ?",
            "why_asked": "Verifier ton sens du levier et ton pragmatisme.",
            "answer_shape": "Frequence, temps perdu, risque d'erreur, impact sur l'equipe.",
        },
        {
            "question": "Parle-moi d'un process que tu as simplifie ou structure.",
            "why_asked": "Mesurer ton orientation execution et clarté.",
            "answer_shape": "Avant, irritant, intervention, apres, gain observe.",
        },
    ],
}


class PortfolioImportError(RuntimeError):
    pass


def _normalize_text(value: str) -> str:
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9\+\#\.]+", " ", normalized.lower()).strip()


def _normalize_url(url: str) -> str:
    clean = sanitize_line(url, 220)
    if not clean:
        raise PortfolioImportError("Portfolio URL is required")
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"
    return clean


def _meta_content(soup: BeautifulSoup, attr: str, value: str) -> str:
    tag = soup.find("meta", attrs={attr: value})
    if not tag:
        return ""
    return sanitize_line(tag.get("content"), 240)


def _extract_known_skills(text: str, max_items: int = 18) -> list[str]:
    normalized = _normalize_text(text)
    found = []
    for skill in COMMON_TECH:
        skill_norm = _normalize_text(skill)
        if not skill_norm:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(skill_norm)}(?![a-z0-9])", normalized) and skill not in found:
            found.append(skill)
        if len(found) >= max_items:
            break
    return found


def _dedupe_projects(projects: list[dict], max_items: int = 10) -> list[dict]:
    seen = set()
    cleaned = []
    for project in projects:
        name = sanitize_line(project.get("name"), 140)
        url = sanitize_line(project.get("url"), 220)
        key = (name.lower(), url.lower())
        if not name or key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "name": name,
                "role": sanitize_line(project.get("role"), 120),
                "url": url,
                "summary": sanitize_block(project.get("summary"), 700),
                "highlights": sanitize_string_list(project.get("highlights"), max_items=5, max_length=180),
                "technologies": sanitize_string_list(project.get("technologies"), max_items=10, max_length=80),
                "featured": bool(project.get("featured", False)),
            }
        )
        if len(cleaned) >= max_items:
            break
    return cleaned


def _extract_social_links(soup: BeautifulSoup, base_url: str) -> dict:
    links = {"github": "", "linkedin": "", "email": ""}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        absolute = urljoin(base_url, href)
        lowered = absolute.lower()
        if not links["github"] and "github.com/" in lowered and "/topics/" not in lowered:
            links["github"] = absolute
        elif not links["linkedin"] and "linkedin.com/" in lowered:
            links["linkedin"] = absolute
        elif not links["email"] and lowered.startswith("mailto:"):
            links["email"] = absolute.removeprefix("mailto:")
    return links


def _render_page_with_playwright(url: str) -> str:
    """Use Playwright in a subprocess to render JS-heavy pages and return compact structured data."""
    script = f"""
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto("{url}", wait_until="networkidle", timeout=20000)
    except Exception:
        page.goto("{url}", wait_until="domcontentloaded", timeout=15000)
    payload = {{
        "url": page.url,
        "title": page.title(),
        "meta_description": "",
        "text": page.inner_text("body")[:12000],
        "headings": page.eval_on_selector_all(
            "h1, h2, h3",
            "els => els.map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 24)"
        ),
        "anchors": page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({{href: e.href, text: (e.innerText || e.textContent || '').trim().slice(0, 120)}})).filter(item => item.href).slice(0, 80)"
        ),
        "cards": page.eval_on_selector_all(
            "article, section, [class*='project'], [id*='project'], [class*='card']",
            "els => els.map(e => ({{text: (e.innerText || '').trim().slice(0, 700), href: (e.querySelector('a[href]') || {{}}).href || ''}})).filter(item => item.text && item.text.length > 40).slice(0, 40)"
        ),
    }}
    print(json.dumps(payload))
    browser.close()
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=35,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        if result.returncode != 0 and result.stderr.strip():
            logger.warning("Playwright render stderr for %s: %s", url, result.stderr.strip()[:400])
    except Exception as exc:
        logger.warning("Playwright render failed for %s: %s", url, exc)
    return ""


def _legacy_extract_portfolio_with_claude_disabled(page_text: str, page_links: list[str], url: str) -> dict:
    raise PortfolioImportError("Claude portfolio extraction is disabled; use the heuristic scraper path instead")


def _extract_social_links_from_anchors(anchor_items: list[dict]) -> dict:
    links = {"github": "", "linkedin": "", "email": ""}
    for item in anchor_items or []:
        href = sanitize_line(item.get("href"), 240)
        lowered = href.lower()
        if not links["github"] and "github.com/" in lowered and "/topics/" not in lowered:
            links["github"] = href
        elif not links["linkedin"] and "linkedin.com/" in lowered:
            links["linkedin"] = href
        elif not links["email"] and lowered.startswith("mailto:"):
            links["email"] = href.removeprefix("mailto:")
    return links


def _looks_like_person_name(text: str) -> bool:
    clean = sanitize_line(text, 120)
    if not clean or re.search(r"\d|@|https?://", clean):
        return False
    lowered = clean.lower()
    if any(token in lowered for token in ["portfolio", "projects", "work", "developer", "engineer", "designer", "analyst"]):
        return False
    words = clean.split()
    return 2 <= len(words) <= 4


def _guess_person_name(page_title: str, headings: list[str], page_text: str) -> str:
    for candidate in headings[:6]:
        if _looks_like_person_name(candidate):
            return sanitize_line(candidate, 120)
    title_bits = re.split(r"[\-|•|:|/]", page_title or "")
    for candidate in title_bits[:3]:
        if _looks_like_person_name(candidate):
            return sanitize_line(candidate, 120)
    for candidate in page_text.splitlines()[:8]:
        if _looks_like_person_name(candidate):
            return sanitize_line(candidate, 120)
    return ""


def _extract_brief_narrative(meta_description: str, page_text: str) -> str:
    if meta_description:
        return sanitize_block(meta_description, 600)
    lines = [sanitize_line(line, 220) for line in page_text.splitlines() if sanitize_line(line, 220)]
    summary_lines = []
    for line in lines[:18]:
        lowered = line.lower()
        if any(token in lowered for token in ["projects", "experience", "education", "skills", "contact"]):
            if summary_lines:
                break
            continue
        if len(line) >= 40:
            summary_lines.append(line)
        if len(" ".join(summary_lines)) > 380:
            break
    return sanitize_block(" ".join(summary_lines), 600)


def _build_project_candidate(name: str, summary: str, url: str, source_text: str) -> dict | None:
    clean_name = sanitize_line(name, 140)
    if not clean_name:
        return None
    lowered = clean_name.lower()
    if lowered in {"project", "projects", "selected work", "work", "portfolio"}:
        return None
    return {
        "name": clean_name,
        "role": "",
        "url": sanitize_line(url, 220),
        "summary": sanitize_block(summary, 500),
        "highlights": [],
        "technologies": _extract_known_skills(source_text, max_items=10),
        "featured": False,
    }


def _extract_projects_from_cards(cards: list[dict], anchor_items: list[dict]) -> list[dict]:
    candidates = []
    for card in cards or []:
        text = sanitize_block(card.get("text"), 900)
        if len(text) < 40:
            continue
        lines = [sanitize_line(line, 180) for line in text.splitlines() if sanitize_line(line, 180)]
        if not lines:
            continue
        name = ""
        for line in lines[:4]:
            if 4 <= len(line) <= 80 and not re.search(r"https?://|www\.|@|\b20\d{2}\b", line):
                name = line
                break
        summary = " ".join(lines[1:4]) if len(lines) > 1 else text
        candidate = _build_project_candidate(name or lines[0], summary, card.get("href"), text)
        if candidate and (candidate["technologies"] or len(summary) >= 50):
            candidates.append(candidate)

    for anchor in anchor_items or []:
        text = sanitize_line(anchor.get("text"), 120)
        href = sanitize_line(anchor.get("href"), 220)
        if not text or len(text) < 4 or len(text) > 90:
            continue
        lowered_href = href.lower()
        if not any(token in lowered_href for token in ["/project", "/projects", "/work", "case-study", "#project"]):
            continue
        candidate = _build_project_candidate(text, "", href, text)
        if candidate:
            candidates.append(candidate)
    return _dedupe_projects(candidates, max_items=8)


def _extract_section_entries(page_text: str, keywords: list[str], entry_kind: str) -> list[dict]:
    lines = [sanitize_line(line, 180) for line in page_text.splitlines() if sanitize_line(line, 180)]
    start_index = None
    for index, line in enumerate(lines):
        normalized = _normalize_text(line)
        if len(line) <= 60 and any(keyword in normalized for keyword in keywords):
            start_index = index + 1
            break
    if start_index is None:
        return []

    section_lines = []
    for line in lines[start_index : start_index + 32]:
        normalized = _normalize_text(line)
        if len(line) <= 60 and any(
            token in normalized
            for token in ["project", "projects", "skills", "competence", "contact", "education", "formation", "experience"]
        ):
            break
        section_lines.append(line)

    blocks = []
    current = []
    for line in section_lines:
        if current and len(line) <= 80 and (re.search(r"\b20\d{2}\b", line) or len(current) >= 3):
            blocks.append(current)
            current = [line]
            continue
        current.append(line)
    if current:
        blocks.append(current)

    entries = []
    for block in blocks[:6]:
        if not block:
            continue
        title = sanitize_line(block[0], 140)
        summary = sanitize_block(" ".join(block[1:4]), 400)
        if entry_kind == "education":
            entries.append({"school": title, "degree": "", "field": "", "summary": summary})
        else:
            entries.append({"title": title, "company": "", "summary": summary})
    return entries


def _github_path_parts(url: str) -> list[str]:
    raw = sanitize_line(url, 300)
    if not raw:
        return []

    if raw.startswith("git@github.com:"):
        path = raw.split(":", 1)[1]
        parts = [part for part in path.split("/") if part]
    else:
        parsed = urlparse(raw)
        if "github.com" not in parsed.netloc.lower():
            return []
        parts = [part for part in parsed.path.split("/") if part]

    if parts and parts[-1].lower().endswith(".git"):
        parts[-1] = parts[-1][:-4]
    return parts


def _github_username_from_url(url: str) -> str:
    parts = _github_path_parts(url)
    return parts[0] if parts else ""


def _github_repo_from_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) if the URL points to a specific GitHub repo."""
    parts = _github_path_parts(url)
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", ""


def _extract_balanced_block(text: str, start_index: int, open_char: str, close_char: str) -> str:
    if start_index < 0 or start_index >= len(text) or text[start_index] != open_char:
        return ""
    depth = 0
    quote = ""
    escaped = False
    for index in range(start_index, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]
    return ""


def _js_unescape(value: str) -> str:
    if not value:
        return ""
    text = value
    text = re.sub(
        r"\\u\{([0-9a-fA-F]+)\}",
        lambda match: chr(int(match.group(1), 16)),
        text,
    )
    text = re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda match: chr(int(match.group(1), 16)),
        text,
    )
    replacements = {
        r"\\n": "\n",
        r"\\r": "\r",
        r"\\t": "\t",
        r'\\"': '"',
        r"\\'": "'",
        r"\\\\": "\\",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _extract_js_string_field(block: str, field_name: str) -> str:
    pattern = re.compile(rf"{re.escape(field_name)}\s*:\s*(['\"])(.*?)\1", re.S)
    match = pattern.search(block)
    if not match:
        return ""
    return sanitize_line(_js_unescape(match.group(2)), 220)


def _extract_js_localized_field(block: str, field_name: str) -> str:
    match = re.search(rf"{re.escape(field_name)}\s*:\s*\{{", block)
    if not match:
        return ""
    obj_block = _extract_balanced_block(block, match.end() - 1, "{", "}")
    if not obj_block:
        return ""
    for locale in ["fr", "en"]:
        value = _extract_js_string_field(obj_block, locale)
        if value:
            return value
    return ""


def _extract_projects_array_blocks(source_text: str) -> list[str]:
    match = re.search(r"projects\s*=\s*\[", source_text)
    if not match:
        return []
    array_block = _extract_balanced_block(source_text, match.end() - 1, "[", "]")
    if not array_block:
        return []

    items = []
    index = 0
    while index < len(array_block):
        if array_block[index] == "{":
            item = _extract_balanced_block(array_block, index, "{", "}")
            if item:
                items.append(item)
                index += len(item)
                continue
        index += 1
    return items


def _extract_projects_from_github_source(source_text: str) -> list[dict]:
    projects = []
    for block in _extract_projects_array_blocks(source_text):
        name = _extract_js_localized_field(block, "title") or _extract_js_string_field(block, "title")
        summary = _extract_js_localized_field(block, "desc") or _extract_js_localized_field(block, "tagline")
        role_slug = _extract_js_string_field(block, "jobRole").lower()
        role = GITHUB_ROLE_LABELS.get(role_slug, sanitize_line(role_slug.replace("-", " ").title(), 120))
        result = _extract_js_localized_field(block, "result")
        sector = _extract_js_localized_field(block, "sector")
        link = _extract_js_string_field(block, "link")
        technologies = _extract_known_skills(" ".join([block, summary, result, sector]), max_items=8)
        highlights = sanitize_string_list([result, sector], max_items=4, max_length=120)
        if not name or len(summary) < 10:
            continue
        projects.append(
            {
                "name": sanitize_line(name, 140),
                "role": sanitize_line(role, 120),
                "url": link if link.startswith(("http://", "https://")) else "",
                "summary": sanitize_block(summary, 500),
                "highlights": highlights,
                "technologies": technologies,
                "featured": True,
            }
        )
    return _dedupe_projects(projects, max_items=12)


def _fetch_github_repo_project_source(owner: str, repo: str, gh_headers: dict) -> tuple[str, str]:
    for path in GITHUB_PROJECT_FILE_CANDIDATES:
        try:
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                headers={**gh_headers, "Accept": "application/vnd.github.raw+json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.ok and response.text.strip():
                return path, response.text[:50000]
        except Exception:
            continue
    return "", ""


def _fetch_github_repo_portfolio(owner: str, repo: str) -> dict:
    """Extract portfolio data from a specific GitHub repo."""
    gh_headers = {"Accept": "application/vnd.github+json", **REQUEST_HEADERS}

    # Fetch repo metadata
    repo_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=gh_headers, timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not repo_resp.ok:
        raise PortfolioImportError(f"GitHub repo {owner}/{repo} not found")
    repo_data = repo_resp.json()

    # Fetch README content
    readme_text = ""
    try:
        readme_resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers={**gh_headers, "Accept": "application/vnd.github.raw+json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if readme_resp.ok:
            readme_text = readme_resp.text[:10000]
    except Exception:
        pass

    # Fetch user profile for name/bio
    user_resp = requests.get(
        f"https://api.github.com/users/{owner}",
        headers=gh_headers, timeout=REQUEST_TIMEOUT_SECONDS,
    )
    user = user_resp.json() if user_resp.ok else {}

    # Fetch languages used in the repo
    languages = []
    try:
        lang_resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/languages",
            headers=gh_headers, timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if lang_resp.ok:
            languages = list(lang_resp.json().keys())[:12]
    except Exception:
        pass
    if not languages and repo_data.get("language"):
        languages = [repo_data["language"]]

    project_source_path, project_source_text = _fetch_github_repo_project_source(owner, repo, gh_headers)
    source_projects = _extract_projects_from_github_source(project_source_text) if project_source_text else []

    # Fallback: fetch other repos from this user when the portfolio repo does not expose project data.
    other_projects = []
    if not source_projects:
        try:
            repos_resp = requests.get(
                f"https://api.github.com/users/{owner}/repos?per_page=30&type=owner&sort=updated",
                headers=gh_headers, timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if repos_resp.ok:
                for r in repos_resp.json():
                    if r.get("fork") or r.get("name") == repo:
                        continue
                    techs = [r["language"]] if r.get("language") else []
                    other_projects.append({
                        "name": r.get("name", "").replace("-", " ").strip() or "GitHub project",
                        "role": "Repository owner",
                        "url": r.get("homepage") or r.get("html_url") or "",
                        "summary": r.get("description") or "GitHub repository",
                        "highlights": [
                            detail for detail in [
                                f"{r.get('stargazers_count', 0)} stars" if r.get("stargazers_count") else "",
                                "Has live demo" if r.get("homepage") else "",
                            ] if detail
                        ],
                        "technologies": techs,
                        "featured": False,
                    })
        except Exception:
            pass

    # Parse README for skills and structure
    all_skills = sanitize_string_list(
        [
            *languages,
            *_extract_known_skills(readme_text, max_items=20),
            *_extract_known_skills(project_source_text, max_items=20),
            *[tech for project in source_projects for tech in project.get("technologies", [])],
        ],
        max_items=24, max_length=80,
    )

    # Main project from the repo itself
    main_project = {
        "name": repo_data.get("name", "").replace("-", " ").strip() or "Portfolio repo",
        "role": "Repository owner",
        "url": repo_data.get("homepage") or repo_data.get("html_url") or "",
        "summary": repo_data.get("description") or "GitHub portfolio repository",
        "highlights": [
            detail for detail in [
                f"{repo_data.get('stargazers_count', 0)} stars" if repo_data.get("stargazers_count") else "",
                "Has live demo" if repo_data.get("homepage") else "",
            ] if detail
        ],
        "technologies": languages[:8],
        "featured": True,
    }

    projects = source_projects or _dedupe_projects([main_project, *other_projects])
    narrative = sanitize_block(repo_data.get("description") or user.get("bio") or "", 600)
    if readme_text and len(narrative) < 100:
        # Take first paragraph of README as narrative
        for line in readme_text.split("\n"):
            clean = line.strip().lstrip("#").strip()
            if len(clean) > 40 and not clean.startswith(("!", "[", "|", "```", "---")):
                narrative = sanitize_block(clean, 600)
                break
    if source_projects and len(narrative) < 100:
        narrative = sanitize_block(
            repo_data.get("description")
            or f"Portfolio source repository with {len(source_projects)} structured projects extracted from {project_source_path}.",
            600,
        )

    return {
        "source_url": repo_data.get("html_url") or f"https://github.com/{owner}/{repo}",
        "final_url": repo_data.get("html_url") or f"https://github.com/{owner}/{repo}",
        "domain": "github.com",
        "page_title": sanitize_line(user.get("name") or owner, 140),
        "person_name": sanitize_line(user.get("name"), 120),
        "meta_description": sanitize_block(user.get("bio"), 240),
        "narrative": narrative,
        "skills": all_skills,
        "projects": projects,
        "links": {
            "github": user.get("html_url") or f"https://github.com/{owner}",
            "linkedin": "",
            "email": sanitize_line(user.get("email"), 120),
        },
        "headings": sanitize_string_list([project_source_path] if project_source_path else [], max_items=4, max_length=120),
        "captured_at": datetime.utcnow().isoformat(),
    }


def _fetch_github_profile(username: str) -> dict:
    gh_headers = {"Accept": "application/vnd.github+json", **REQUEST_HEADERS}

    user_resp = requests.get(
        f"https://api.github.com/users/{username}",
        headers=gh_headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not user_resp.ok:
        raise PortfolioImportError("GitHub profile could not be fetched")

    repos_resp = requests.get(
        f"https://api.github.com/users/{username}/repos?per_page=100&type=owner&sort=updated",
        headers=gh_headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not repos_resp.ok:
        raise PortfolioImportError("GitHub repositories could not be fetched")

    user = user_resp.json()
    repos = repos_resp.json()
    projects = []
    for repo in repos:
        if repo.get("fork"):
            continue
        technologies = []
        if repo.get("language"):
            technologies.append(repo["language"])
        projects.append(
            {
                "name": repo.get("name", "").replace("-", " ").strip() or "GitHub project",
                "role": "Repository owner",
                "url": repo.get("homepage") or repo.get("html_url") or "",
                "summary": repo.get("description") or "GitHub repository",
                "highlights": [
                    detail
                    for detail in [
                        f"{repo.get('stargazers_count', 0)} stars" if repo.get("stargazers_count") else "",
                        "Has live demo" if repo.get("homepage") else "",
                    ]
                    if detail
                ],
                "technologies": technologies,
                "featured": False,
            }
        )

    return {
        "source_url": user.get("html_url") or f"https://github.com/{username}",
        "final_url": user.get("html_url") or f"https://github.com/{username}",
        "domain": "github.com",
        "page_title": sanitize_line(user.get("name") or username, 140),
        "person_name": sanitize_line(user.get("name"), 120),
        "meta_description": sanitize_block(user.get("bio"), 240),
        "narrative": sanitize_block(user.get("bio"), 600),
        "skills": [],
        "projects": _dedupe_projects(projects),
        "links": {
            "github": user.get("html_url") or f"https://github.com/{username}",
            "linkedin": "",
            "email": "",
        },
        "headings": [],
        "captured_at": datetime.utcnow().isoformat(),
    }


def _merge_social_links(*link_sets: dict | None) -> dict:
    merged = {"github": "", "linkedin": "", "email": ""}
    for link_set in link_sets:
        if not isinstance(link_set, dict):
            continue
        for key in merged:
            value = sanitize_line((link_set or {}).get(key), 220 if key != "email" else 120)
            if value and not merged[key]:
                merged[key] = value
    return merged


def _sanitize_anchor_items(anchor_items: list[dict], base_url: str) -> list[dict]:
    cleaned = []
    for item in anchor_items or []:
        href = sanitize_line(item.get("href"), 240)
        if not href:
            continue
        cleaned.append(
            {
                "href": urljoin(base_url, href),
                "text": sanitize_line(item.get("text"), 120),
            }
        )
        if len(cleaned) >= 80:
            break
    return cleaned


def _sanitize_card_items(cards: list[dict], base_url: str) -> list[dict]:
    cleaned = []
    for card in cards or []:
        text = sanitize_block(card.get("text"), 700)
        href = sanitize_line(card.get("href"), 240)
        if not text:
            continue
        cleaned.append({"text": text, "href": urljoin(base_url, href) if href else ""})
        if len(cleaned) >= 40:
            break
    return cleaned


def _fetch_page_snapshot(url: str) -> dict:
    rendered_data = _render_page_with_playwright(url)
    page_text = ""
    page_title = ""
    page_headings = []
    anchor_items = []
    page_cards = []
    meta_description = ""
    final_url = url
    soup_links = {}

    if rendered_data:
        try:
            parsed = json.loads(rendered_data)
            final_url = sanitize_line(parsed.get("url"), 220) or final_url
            page_text = sanitize_block(parsed.get("text"), 12000)
            page_title = sanitize_line(parsed.get("title"), 180)
            meta_description = sanitize_block(parsed.get("meta_description"), 240)
            page_headings = sanitize_string_list(parsed.get("headings"), max_items=24, max_length=120)
            anchor_items = _sanitize_anchor_items(parsed.get("anchors", []), final_url)
            page_cards = _sanitize_card_items(parsed.get("cards", []), final_url)
        except Exception:
            page_text = sanitize_block(rendered_data, 12000)

    if not page_text or len(page_text.strip()) < 100 or not meta_description or not anchor_items:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.ok:
            final_url = sanitize_line(response.url, 220) or final_url
            soup = parse_html(response.text)
            for tag_name in ["script", "style", "noscript", "svg"]:
                for node in soup.find_all(tag_name):
                    node.decompose()
            main = soup.find("main") or soup.body or soup
            request_text = sanitize_block(main.get_text(" ", strip=True), 10000)
            if len(request_text) > len(page_text):
                page_text = request_text
            page_title = page_title or sanitize_line((soup.title.string if soup.title and soup.title.string else ""), 180)
            meta_description = meta_description or (
                _meta_content(soup, "name", "description") or _meta_content(soup, "property", "og:description")
            )
            if not page_headings:
                page_headings = sanitize_string_list(
                    [node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2", "h3"])],
                    max_items=24,
                    max_length=120,
                )
            if not anchor_items:
                anchor_items = _sanitize_anchor_items(
                    [{"href": anchor.get("href", ""), "text": anchor.get_text(" ", strip=True)} for anchor in soup.find_all("a", href=True)],
                    final_url,
                )
            if not page_cards:
                page_cards = _sanitize_card_items(
                    [
                        {
                            "text": node.get_text("\n", strip=True),
                            "href": first_anchor.get("href", "") if (first_anchor := node.find("a", href=True)) else "",
                        }
                        for node in soup.find_all(["article", "section"])
                    ],
                    final_url,
                )
            soup_links = _extract_social_links(soup, final_url)

    if not page_text or len(page_text.strip()) < 50:
        raise PortfolioImportError("Portfolio page returned no readable content")

    return {
        "requested_url": url,
        "final_url": final_url,
        "page_title": page_title,
        "meta_description": meta_description,
        "text": page_text,
        "headings": page_headings,
        "anchors": anchor_items,
        "cards": page_cards,
        "links": _merge_social_links(_extract_social_links_from_anchors(anchor_items), soup_links),
    }


def _same_domain_url(reference_url: str, candidate_url: str) -> bool:
    reference_host = urlparse(reference_url or "").netloc.lower().removeprefix("www.")
    candidate_host = urlparse(candidate_url or "").netloc.lower().removeprefix("www.")
    return bool(reference_host and candidate_host and reference_host == candidate_host)


def _score_candidate_portfolio_link(base_url: str, item: dict) -> int:
    href = sanitize_line(item.get("href"), 240)
    text = sanitize_line(item.get("text"), 120)
    if not href or any(href.lower().startswith(prefix) for prefix in ["mailto:", "tel:", "javascript:"]):
        return -1
    if not _same_domain_url(base_url, href):
        return -1
    lowered_href = href.lower()
    if any(lowered_href.endswith(ext) for ext in PORTFOLIO_LINK_SKIP_EXTENSIONS):
        return -1

    parsed = urlparse(href)
    if parsed.fragment and not parsed.path.strip("/"):
        return -1

    haystack = _normalize_text(f"{parsed.path} {text}")
    score = 0
    if any(token in haystack for token in PORTFOLIO_LINK_HINTS):
        score += 2
    if any(token in haystack for token in ["project", "projects", "work", "case", "study"]):
        score += 7
    if any(token in haystack for token in ["portfolio", "selected work"]):
        score += 5
    if any(token in haystack for token in ["about", "experience", "resume", "cv"]):
        score += 3
    if any(token in haystack for token in ["blog", "post", "article"]):
        score -= 4
    if text and 3 <= len(text) <= 90:
        score += 1
    return score


def _collect_portfolio_pages(normalized_url: str) -> list[dict]:
    primary_page = _fetch_page_snapshot(normalized_url)
    pages = [primary_page]
    seen = {
        sanitize_line(normalized_url.split("#")[0].rstrip("/"), 240),
        sanitize_line(primary_page.get("final_url", "").split("#")[0].rstrip("/"), 240),
    }
    candidates = []
    for item in primary_page.get("anchors") or []:
        score = _score_candidate_portfolio_link(primary_page.get("final_url") or normalized_url, item)
        if score <= 0:
            continue
        href = sanitize_line(item.get("href"), 240)
        canonical = sanitize_line(href.split("#")[0].rstrip("/"), 240)
        if not canonical or canonical in seen:
            continue
        candidates.append((score, href))

    for _, href in sorted(candidates, key=lambda row: (-row[0], row[1])):
        if len(pages) >= PORTFOLIO_PAGE_LIMIT:
            break
        canonical = sanitize_line(href.split("#")[0].rstrip("/"), 240)
        if not canonical or canonical in seen:
            continue
        try:
            page = _fetch_page_snapshot(href)
        except Exception as exc:
            logger.warning("Portfolio subpage fetch failed for %s: %s", href, exc)
            seen.add(canonical)
            continue
        pages.append(page)
        seen.add(canonical)
        seen.add(sanitize_line((page.get("final_url") or "").split("#")[0].rstrip("/"), 240))
    return pages


def _dedupe_experience_entries(entries: list[dict], max_items: int = 10) -> list[dict]:
    seen = set()
    cleaned = []
    for raw in entries or []:
        if not isinstance(raw, dict):
            continue
        item = {
            "company": sanitize_line(raw.get("company"), 120),
            "title": sanitize_line(raw.get("title"), 140),
            "location": sanitize_line(raw.get("location"), 120),
            "start_date": sanitize_line(raw.get("start_date"), 40),
            "end_date": sanitize_line(raw.get("end_date"), 40),
            "summary": sanitize_block(raw.get("summary"), 800),
            "highlights": sanitize_string_list(raw.get("highlights"), max_items=6, max_length=180),
            "skills": sanitize_string_list(raw.get("skills"), max_items=12, max_length=80),
        }
        key = (
            item["company"].lower(),
            item["title"].lower(),
            item["start_date"].lower(),
            item["end_date"].lower(),
        )
        if not (item["company"] or item["title"]) or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _dedupe_education_entries(entries: list[dict], max_items: int = 6) -> list[dict]:
    seen = set()
    cleaned = []
    for raw in entries or []:
        if not isinstance(raw, dict):
            continue
        item = {
            "school": sanitize_line(raw.get("school"), 120),
            "degree": sanitize_line(raw.get("degree"), 120),
            "field": sanitize_line(raw.get("field"), 120),
            "summary": sanitize_block(raw.get("summary"), 400),
        }
        key = (item["school"].lower(), item["degree"].lower(), item["field"].lower())
        if not (item["school"] or item["degree"] or item["field"]) or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _build_heuristic_portfolio_snapshot(normalized_url: str, pages: list[dict]) -> dict:
    primary_page = pages[0] if pages else {}
    final_url = primary_page.get("final_url") or normalized_url
    all_text = "\n\n".join(page.get("text", "") for page in pages if page.get("text"))
    all_headings = sanitize_string_list(
        [heading for page in pages for heading in (page.get("headings") or [])],
        max_items=24,
        max_length=120,
    )
    all_anchors = [anchor for page in pages for anchor in (page.get("anchors") or [])][:160]
    all_cards = [card for page in pages for card in (page.get("cards") or [])][:80]
    links = _merge_social_links(*[page.get("links") for page in pages], _extract_social_links_from_anchors(all_anchors))
    projects = _extract_projects_from_cards(all_cards, all_anchors)

    if links.get("github") and len(projects) < 3:
        try:
            gh_username = _github_username_from_url(links["github"])
            if gh_username:
                github_snapshot = _fetch_github_profile(gh_username)
                projects = _dedupe_projects([*projects, *(github_snapshot.get("projects") or [])])
        except Exception:
            pass

    skills = sanitize_string_list(
        [
            *_extract_known_skills(all_text, max_items=18),
            *[tech for project in projects for tech in project.get("technologies", [])],
        ],
        max_items=24,
        max_length=80,
    )
    page_title = (
        primary_page.get("page_title")
        or next((page.get("page_title") for page in pages if page.get("page_title")), "")
    )
    meta_description = (
        primary_page.get("meta_description")
        or next((page.get("meta_description") for page in pages if page.get("meta_description")), "")
    )
    person_name = _guess_person_name(page_title, all_headings, all_text)
    narrative = _extract_brief_narrative(meta_description, all_text)
    domain = urlparse(final_url).netloc.replace("www.", "")

    experience = _dedupe_experience_entries(
        _extract_section_entries(all_text, ["experience", "work", "internship", "stage", "alternance"], "experience")
    )
    education = _dedupe_education_entries(
        _extract_section_entries(all_text, ["education", "formation", "school", "university"], "education")
    )

    return {
        "source_url": normalized_url,
        "final_url": final_url,
        "domain": domain,
        "page_title": page_title or person_name or domain,
        "person_name": person_name,
        "meta_description": meta_description or (narrative[:240] if narrative else ""),
        "narrative": narrative,
        "skills": skills,
        "projects": projects,
        "links": links,
        "headings": all_headings,
        "experience": experience,
        "education": education,
        "source_pages": [page.get("final_url") or page.get("requested_url") for page in pages if page.get("final_url") or page.get("requested_url")],
        "captured_at": datetime.utcnow().isoformat(),
        "extraction_method": "heuristic",
    }


def _build_anthropic_portfolio_payload(pages: list[dict], heuristic_snapshot: dict) -> dict:
    return {
        "source_url": heuristic_snapshot.get("source_url"),
        "final_url": heuristic_snapshot.get("final_url"),
        "domain": heuristic_snapshot.get("domain"),
        "known_social_links": heuristic_snapshot.get("links") or {},
        "pages": [
            {
                "url": page.get("final_url") or page.get("requested_url"),
                "title": page.get("page_title"),
                "meta_description": page.get("meta_description"),
                "headings": sanitize_string_list(page.get("headings"), max_items=18, max_length=120),
                "text_excerpt": sanitize_block(page.get("text"), PORTFOLIO_PAGE_TEXT_LIMIT),
                "anchors": [
                    {"text": sanitize_line(item.get("text"), 120), "href": sanitize_line(item.get("href"), 240)}
                    for item in (page.get("anchors") or [])[:24]
                ],
                "cards": [
                    {"href": sanitize_line(item.get("href"), 240), "text": sanitize_block(item.get("text"), 320)}
                    for item in (page.get("cards") or [])[:12]
                ],
            }
            for page in pages[:PORTFOLIO_PAGE_LIMIT]
        ],
    }


def _sanitize_anthropic_portfolio_snapshot(snapshot: dict | None) -> dict:
    cleaned = snapshot if isinstance(snapshot, dict) else {}
    return {
        "person_name": sanitize_line(cleaned.get("person_name"), 120),
        "page_title": sanitize_line(cleaned.get("page_title"), 180),
        "meta_description": sanitize_block(cleaned.get("meta_description"), 240),
        "narrative": sanitize_block(cleaned.get("narrative"), 600),
        "skills": sanitize_string_list(cleaned.get("skills"), max_items=24, max_length=80),
        "headings": sanitize_string_list(cleaned.get("headings"), max_items=24, max_length=120),
        "links": _merge_social_links(cleaned.get("links")),
        "projects": _dedupe_projects(cleaned.get("projects") or [], max_items=10),
        "experience": _dedupe_experience_entries(cleaned.get("experience") or []),
        "education": _dedupe_education_entries(cleaned.get("education") or []),
        "notes": sanitize_string_list(cleaned.get("notes"), max_items=8, max_length=200),
    }


def _merge_portfolio_snapshots(heuristic_snapshot: dict, anthropic_snapshot: dict) -> dict:
    ai_snapshot = _sanitize_anthropic_portfolio_snapshot(anthropic_snapshot)
    projects = _dedupe_projects(
        [*(ai_snapshot.get("projects") or []), *(heuristic_snapshot.get("projects") or [])],
        max_items=10,
    )
    experience = _dedupe_experience_entries(
        [*(ai_snapshot.get("experience") or []), *(heuristic_snapshot.get("experience") or [])]
    )
    education = _dedupe_education_entries(
        [*(ai_snapshot.get("education") or []), *(heuristic_snapshot.get("education") or [])]
    )
    links = _merge_social_links(ai_snapshot.get("links"), heuristic_snapshot.get("links"))
    headings = sanitize_string_list(
        [*(ai_snapshot.get("headings") or []), *(heuristic_snapshot.get("headings") or [])],
        max_items=24,
        max_length=120,
    )
    skills = sanitize_string_list(
        [
            *(ai_snapshot.get("skills") or []),
            *(heuristic_snapshot.get("skills") or []),
            *[tech for project in projects for tech in project.get("technologies", [])],
        ],
        max_items=24,
        max_length=80,
    )
    narrative = ai_snapshot.get("narrative") or heuristic_snapshot.get("narrative") or ""

    return {
        **heuristic_snapshot,
        "page_title": ai_snapshot.get("page_title") or heuristic_snapshot.get("page_title"),
        "person_name": ai_snapshot.get("person_name") or heuristic_snapshot.get("person_name"),
        "meta_description": (
            ai_snapshot.get("meta_description")
            or heuristic_snapshot.get("meta_description")
            or (narrative[:240] if narrative else "")
        ),
        "narrative": narrative,
        "skills": skills,
        "projects": projects,
        "links": links,
        "headings": headings,
        "experience": experience,
        "education": education,
        "notes": sanitize_string_list(
            [*(ai_snapshot.get("notes") or []), *(heuristic_snapshot.get("notes") or [])],
            max_items=8,
            max_length=200,
        ),
        "extraction_method": "anthropic",
    }


def _legacy_scrape_portfolio_heuristic_only(portfolio_url: str) -> dict:
    normalized_url = _normalize_url(portfolio_url)

    # GitHub repo URL (e.g., github.com/user/repo) → use API directly, no Claude needed
    owner, repo = _github_repo_from_url(normalized_url)
    if owner and repo:
        return _fetch_github_repo_portfolio(owner, repo)

    # GitHub profile URL (e.g., github.com/user) → use API directly
    username = _github_username_from_url(normalized_url)
    if username and urlparse(normalized_url).path.strip("/").count("/") == 0:
        return _fetch_github_profile(username)

    # ── Step 1: Try Playwright render for JS-heavy sites (SPAs, React, etc.) ──
    rendered_data = _render_page_with_playwright(normalized_url)
    page_text = ""
    page_title = ""
    page_headings = []
    anchor_items = []
    page_cards = []
    if rendered_data:
        try:
            parsed = json.loads(rendered_data)
            page_text = parsed.get("text", "")
            page_title = sanitize_line(parsed.get("title"), 180)
            page_headings = sanitize_string_list(parsed.get("headings"), max_items=24, max_length=120)
            anchor_items = parsed.get("anchors", [])[:80]
            page_cards = parsed.get("cards", [])[:40]
        except Exception:
            page_text = rendered_data

    final_url = normalized_url
    meta_description = ""
    links = {}
    if not page_text or len(page_text.strip()) < 100:
        try:
            response = requests.get(normalized_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.ok:
                final_url = response.url
                soup = parse_html(response.text)
                for tag_name in ["script", "style", "noscript", "svg"]:
                    for node in soup.find_all(tag_name):
                        node.decompose()
                main = soup.find("main") or soup.body or soup
                page_text = sanitize_block(main.get_text(" ", strip=True), 10000)
                page_title = page_title or sanitize_line((soup.title.string if soup.title and soup.title.string else ""), 180)
                meta_description = _meta_content(soup, "name", "description") or _meta_content(soup, "property", "og:description")
                page_headings = page_headings or sanitize_string_list(
                    [node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2", "h3"])],
                    max_items=24,
                    max_length=120,
                )
                anchor_items = anchor_items or [
                    {
                        "href": urljoin(final_url, anchor.get("href", "")),
                        "text": sanitize_line(anchor.get_text(" ", strip=True), 120),
                    }
                    for anchor in soup.find_all("a", href=True)[:80]
                ]
                page_cards = page_cards or [
                    {
                        "text": sanitize_block(node.get_text("\n", strip=True), 700),
                        "href": urljoin(final_url, first_anchor.get("href", "")) if (first_anchor := node.find("a", href=True)) else "",
                    }
                    for node in soup.find_all(["article", "section"])[:40]
                    if sanitize_block(node.get_text("\n", strip=True), 700)
                ]
                links = _extract_social_links(soup, final_url)
        except Exception as exc:
            if not page_text:
                raise PortfolioImportError(f"Could not fetch portfolio: {exc}")

    if not page_text or len(page_text.strip()) < 50:
        raise PortfolioImportError("Portfolio page returned no readable content")

    links = {**_extract_social_links_from_anchors(anchor_items), **links}
    projects = _extract_projects_from_cards(page_cards, anchor_items)

    # If GitHub link found and few projects, enrich from GitHub API
    if links.get("github") and len(projects) < 3:
        try:
            gh_username = _github_username_from_url(links["github"])
            if gh_username:
                github_snapshot = _fetch_github_profile(gh_username)
                projects = _dedupe_projects([*projects, *(github_snapshot.get("projects") or [])])
        except Exception:
            pass

    skills = sanitize_string_list(
        [
            *_extract_known_skills(page_text, max_items=18),
            *[tech for project in projects for tech in project.get("technologies", [])],
        ],
        max_items=24,
        max_length=80,
    )

    person_name = _guess_person_name(page_title, page_headings, page_text)
    narrative = _extract_brief_narrative(meta_description, page_text)
    domain = urlparse(final_url).netloc.replace("www.", "")
    experience = _extract_section_entries(page_text, ["experience", "work", "internship", "stage", "alternance"], "experience")
    education = _extract_section_entries(page_text, ["education", "formation", "school", "university"], "education")

    return {
        "source_url": normalized_url,
        "final_url": final_url,
        "domain": domain,
        "page_title": page_title or person_name or domain,
        "person_name": person_name,
        "meta_description": meta_description or (narrative[:240] if narrative else ""),
        "narrative": narrative,
        "skills": skills,
        "projects": projects,
        "links": links,
        "headings": page_headings,
        "experience": experience,
        "education": education,
        "captured_at": datetime.utcnow().isoformat(),
    }


def scrape_portfolio(portfolio_url: str) -> dict:
    normalized_url = _normalize_url(portfolio_url)

    owner, repo = _github_repo_from_url(normalized_url)
    if owner and repo:
        return _fetch_github_repo_portfolio(owner, repo)

    username = _github_username_from_url(normalized_url)
    if username and urlparse(normalized_url).path.strip("/").count("/") == 0:
        return _fetch_github_profile(username)

    try:
        pages = _collect_portfolio_pages(normalized_url)
    except requests.RequestException as exc:
        raise PortfolioImportError(f"Could not fetch portfolio: {exc}") from exc

    heuristic_snapshot = _build_heuristic_portfolio_snapshot(normalized_url, pages)

    try:
        anthropic_snapshot = extract_portfolio_snapshot(_build_anthropic_portfolio_payload(pages, heuristic_snapshot))
    except Exception as exc:
        logger.warning("Anthropic portfolio extraction failed for %s: %s", normalized_url, exc)
        return heuristic_snapshot

    merged_snapshot = _merge_portfolio_snapshots(heuristic_snapshot, anthropic_snapshot)
    if not merged_snapshot.get("projects") and heuristic_snapshot.get("projects"):
        return heuristic_snapshot
    return merged_snapshot


def merge_portfolio_into_profile(profile: dict, snapshot: dict) -> dict:
    merged = dict(profile)
    merged["portfolio_url"] = snapshot.get("final_url") or snapshot.get("source_url") or merged.get("portfolio_url", "")
    if not merged.get("website"):
        merged["website"] = merged["portfolio_url"]
    links = snapshot.get("links") or {}
    if not merged.get("github") and links.get("github"):
        merged["github"] = links["github"]
    if not merged.get("linkedin") and links.get("linkedin"):
        merged["linkedin"] = links["linkedin"]
    if not merged.get("email") and links.get("email"):
        merged["email"] = links["email"]
    if not merged.get("full_name") and snapshot.get("person_name"):
        merged["full_name"] = snapshot["person_name"]
    if not merged.get("summary") and snapshot.get("narrative"):
        merged["summary"] = snapshot["narrative"]
    merged["skills"] = sanitize_string_list(
        [
            *(profile.get("skills") or []),
            *(snapshot.get("skills") or []),
            *[tech for project in snapshot.get("projects") or [] for tech in project.get("technologies", [])],
        ],
        max_items=40,
        max_length=80,
    )
    merged_projects = list(profile.get("projects") or [])
    for project in snapshot.get("projects") or []:
        merged_projects.append(
            {
                "name": project.get("name", ""),
                "role": project.get("role", ""),
                "url": project.get("url", ""),
                "summary": project.get("summary", ""),
                "highlights": project.get("highlights") or [],
                "technologies": project.get("technologies") or [],
                "featured": False,
            }
        )
    merged["projects"] = _dedupe_projects(merged_projects, max_items=20)

    # Merge experience from portfolio if user has none
    if not merged.get("experience") and snapshot.get("experience"):
        merged["experience"] = [
            {
                "id": f"portfolio-{i}",
                "company": sanitize_line(exp.get("company"), 120),
                "title": sanitize_line(exp.get("title"), 140),
                "location": sanitize_line(exp.get("location"), 120),
                "start_date": sanitize_line(exp.get("start_date"), 40),
                "end_date": sanitize_line(exp.get("end_date"), 40),
                "summary": sanitize_block(exp.get("summary"), 800),
                "highlights": [],
                "skills": [],
                "featured": False,
            }
            for i, exp in enumerate(snapshot["experience"][:10])
            if exp.get("title") or exp.get("company")
        ]

    # Merge education from portfolio if user has none
    if not merged.get("education") and snapshot.get("education"):
        merged["education"] = [
            {
                "id": f"portfolio-edu-{i}",
                "school": sanitize_line(edu.get("school"), 120),
                "degree": sanitize_line(edu.get("degree"), 120),
                "field": sanitize_line(edu.get("field"), 120),
                "location": "",
                "start_date": "",
                "end_date": "",
                "summary": "",
                "highlights": [],
                "skills": [],
                "featured": False,
            }
            for i, edu in enumerate(snapshot["education"][:6])
            if edu.get("school") or edu.get("degree")
        ]

    return sanitize_cv_profile(merged)


def build_candidate_brief(profile: dict) -> dict:
    snapshot = profile.get("portfolio_snapshot") or {}
    projects = list(profile.get("projects") or [])
    skills = sanitize_string_list(
        [
            *(profile.get("skills") or []),
            *(snapshot.get("skills") or []),
            *[tech for project in projects for tech in project.get("technologies", [])],
        ],
        max_items=12,
        max_length=80,
    )
    summary = profile.get("summary") or snapshot.get("narrative") or sanitize_block(profile.get("cv_text"), 500)
    project_highlights = []
    for project in projects[:4]:
        project_highlights.append(
            {
                "name": project.get("name") or project.get("role") or "Project",
                "summary": sanitize_block(project.get("summary"), 220),
                "technologies": sanitize_string_list(project.get("technologies"), max_items=5, max_length=60),
            }
        )

    strengths = []
    if profile.get("target_roles"):
        strengths.append(f"{len(profile['target_roles'])} target role{'s' if len(profile['target_roles']) > 1 else ''} defined")
    if profile.get("experience"):
        strengths.append(f"{len(profile['experience'])} experiences structured")
    if projects:
        strengths.append(f"{len(projects)} projects in the profile")
    if snapshot.get("projects"):
        strengths.append(f"{len(snapshot['projects'])} projects surfaced from the portfolio")

    return {
        "summary": summary[:520],
        "focus_areas": skills,
        "strengths": strengths[:4],
        "project_highlights": project_highlights,
        "source_health": {
            "has_cv_text": bool(profile.get("cv_text")),
            "has_portfolio": bool(profile.get("portfolio_url")),
            "structured_projects": len(projects),
            "portfolio_projects": len(snapshot.get("projects") or []),
        },
    }


def _match_playbooks(profile: dict) -> list[dict]:
    corpus = " ".join(
        [
            *(profile.get("target_roles") or []),
            profile.get("headline", ""),
            profile.get("summary", ""),
            *(profile.get("skills") or []),
        ]
    )
    normalized = _normalize_text(corpus)
    matches = []
    for playbook in ROLE_PLAYBOOKS:
        if any(keyword in normalized for keyword in playbook["keywords"]):
            matches.append(playbook)
    if not matches:
        matches = ROLE_PLAYBOOKS[:2]
    return matches[:3]


def build_student_guidance(profile: dict) -> dict:
    experiences = profile.get("experience") or []
    projects = profile.get("projects") or []
    playbooks = _match_playbooks(profile)

    story_starters = []
    for item in [*experiences[:3], *projects[:3]]:
        title = item.get("title") or item.get("name") or item.get("company") or "Experience"
        context = item.get("company") or item.get("role") or ""
        story_starters.append(
            {
                "title": sanitize_line(title, 120),
                "when_to_use": (
                    "Question type: raconte-moi un projet dont tu es fier"
                    if item.get("name")
                    else "Question type: parle-moi d'une situation concrete ou tu as contribue"
                ),
                "prompt": (
                    f"Structure {title} en STAR: contexte, objectif, ce que tu as fait toi-meme, resultat, apprentissage."
                ),
                "focus_points": sanitize_string_list(
                    [
                        context,
                        *(item.get("highlights") or []),
                        *(item.get("skills") or item.get("technologies") or []),
                    ],
                    max_items=4,
                    max_length=90,
                ),
            }
        )

    project_ideas = []
    for playbook in playbooks:
        for idea in playbook["ideas"]:
            project_ideas.append(
                {
                    "track": playbook["label"],
                    "title": idea["title"],
                    "brief": idea["brief"],
                    "stack": idea["stack"],
                    "why_it_helps": idea["why_it_helps"],
                }
            )

    return {
        "role_tracks": [playbook["label"] for playbook in playbooks],
        "story_starters": story_starters[:6],
        "project_ideas": project_ideas[:6],
    }


def _top_evidence_refs(profile: dict, limit: int = 4) -> list[str]:
    refs = []
    for item in profile.get("experience") or []:
        label = " - ".join(part for part in [item.get("title"), item.get("company")] if part).strip()
        if label and label not in refs:
            refs.append(label)
        if len(refs) >= limit:
            return refs
    for item in profile.get("projects") or []:
        label = item.get("name") or item.get("role")
        if label and label not in refs:
            refs.append(label)
        if len(refs) >= limit:
            return refs
    return refs


def build_interview_prep(profile: dict) -> dict:
    playbooks = _match_playbooks(profile)
    role_sets = []
    evidence_refs = _top_evidence_refs(profile, limit=5)
    if not evidence_refs:
        evidence_refs = ["Ajoute au moins une experience ou un projet detaille pour t'entrainer proprement"]

    for playbook in playbooks:
        bank = TECHNICAL_QUESTION_BANK.get(playbook["slug"], [])[:2]
        questions = []
        for entry in bank:
            questions.append(
                {
                    "category": playbook["label"],
                    "question": entry["question"],
                    "why_asked": entry["why_asked"],
                    "answer_shape": entry["answer_shape"],
                    "evidence_refs": evidence_refs[:3],
                }
            )
        role_sets.append({"track": playbook["label"], "questions": questions})

    behavioural = []
    guidance = build_student_guidance(profile)
    for item in guidance.get("story_starters", [])[:3]:
        behavioural.append(
            {
                "category": "Behavioural",
                "question": f"Peux-tu raconter {item['title']} en version courte puis detaillee ?",
                "why_asked": "Verifier ta capacite a structurer un exemple reel sans te perdre.",
                "answer_shape": "Version 30 secondes puis STAR complete avec apprentissage.",
                "evidence_refs": item.get("focus_points") or [item.get("title")],
            }
        )

    motivation = []
    for entry in MOTIVATION_QUESTIONS:
        motivation.append(
            {
                **entry,
                "evidence_refs": sanitize_string_list(
                    [
                        *(profile.get("target_roles") or []),
                        profile.get("headline", ""),
                        *(profile.get("skills") or []),
                    ],
                    max_items=3,
                    max_length=80,
                ) or evidence_refs[:2],
            }
        )

    return {
        "practice_plan": [
            "Prepare 2 stories fortes en version 60 secondes.",
            "Prepare 1 exemple technique ou projet par role cible.",
            "Prepare une reponse claire sur pourquoi ce stage maintenant.",
        ],
        "motivation_questions": motivation,
        "behavioural_questions": behavioural,
        "role_question_sets": role_sets,
    }


def build_application_plan(profile: dict) -> dict:
    checklist = [
        {
            "label": "CV master ajoute",
            "done": bool(profile.get("cv_text")),
            "detail": "Colle une version complete pour donner plus de contexte au systeme.",
        },
        {
            "label": "Roles cibles definis",
            "done": bool(profile.get("target_roles")),
            "detail": "2 a 4 roles bien choisis suffisent pour guider les reco.",
        },
        {
            "label": "Portfolio relie",
            "done": bool(profile.get("portfolio_url")),
            "detail": "Le portfolio aide a remonter des projets et des technos plus credibles.",
        },
        {
            "label": "Au moins 2 projets detailes",
            "done": len(profile.get("projects") or []) >= 2,
            "detail": "Mieux vaut 2 bons projets racontables que 6 projets vagues.",
        },
        {
            "label": "Au moins 1 experience exploitable",
            "done": len(profile.get("experience") or []) >= 1,
            "detail": "Stage, asso, freelance ou mission etudiante, tout exemple concret compte.",
        },
        {
            "label": "Resume positionne",
            "done": bool(profile.get("summary")),
            "detail": "Explique ce que tu sais deja faire et ce que tu cherches a apprendre.",
        },
        {
            "label": "Lien pro present",
            "done": bool(profile.get("linkedin") or profile.get("github") or profile.get("website")),
            "detail": "Un lien public suffit pour rassurer sur la presence en ligne.",
        },
    ]

    done_count = sum(1 for item in checklist if item["done"])
    readiness_score = round((done_count / len(checklist)) * 100)

    priority_actions = [item["detail"] for item in checklist if not item["done"]][:4]
    if not priority_actions:
        priority_actions = [
            "Passe 20 minutes a raccourcir tes 2 meilleures stories en version entretien.",
            "Genere un draft cible sur une annonce reelle pour verifier la qualite de la base.",
            "Ameliore un projet portfolio avec des resultats, captures ou lien live.",
        ]

    next_week_plan = [
        "Choisis 10 offres maximum a evaluer au lieu de tout ratisser.",
        "Mets a jour 1 projet portfolio avec une meilleure narration produit ou technique.",
        "Refais 2 stories STAR a voix haute jusqu'a ce qu'elles tiennent en 90 secondes.",
    ]

    return {
        "readiness_score": readiness_score,
        "checklist": checklist,
        "priority_actions": priority_actions,
        "next_week_plan": next_week_plan,
    }
