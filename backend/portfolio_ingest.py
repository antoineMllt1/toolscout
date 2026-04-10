import json
import logging
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

logger = logging.getLogger("toolscout.portfolio")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT_SECONDS = 18
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
        if skill_norm and skill_norm in normalized and skill not in found:
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
        "title": page.title(),
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


def _github_username_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    if "github.com" not in parsed.netloc:
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0] if parts else ""


def _github_repo_from_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) if the URL points to a specific GitHub repo."""
    parsed = urlparse(url or "")
    if "github.com" not in parsed.netloc:
        return "", ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", ""


def _fetch_github_repo_portfolio(owner: str, repo: str) -> dict:
    """Extract portfolio data from a specific GitHub repo (README + repo metadata)."""
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

    # Also fetch other repos from this user for a complete profile
    other_projects = []
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
        [*languages, *_extract_known_skills(readme_text, max_items=20)],
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

    projects = _dedupe_projects([main_project, *other_projects])
    narrative = sanitize_block(repo_data.get("description") or user.get("bio") or "", 600)
    if readme_text and len(narrative) < 100:
        # Take first paragraph of README as narrative
        for line in readme_text.split("\n"):
            clean = line.strip().lstrip("#").strip()
            if len(clean) > 40 and not clean.startswith(("!", "[", "|", "```", "---")):
                narrative = sanitize_block(clean, 600)
                break

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
        "headings": [],
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


def scrape_portfolio(portfolio_url: str) -> dict:
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
                soup = BeautifulSoup(response.text, "lxml")
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
