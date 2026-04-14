import json
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


ANTHROPIC_API_URL = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_TIMEOUT_SECONDS = int(os.environ.get("ANTHROPIC_TIMEOUT_SECONDS", "60"))
ANTHROPIC_FALLBACK_MODELS = [
    "claude-sonnet-4-5",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]


class AnthropicConfigError(RuntimeError):
    pass


class AnthropicResponseError(RuntimeError):
    pass


def _extract_json_block(text: str) -> dict[str, Any]:
    payload = (text or "").strip()
    try:
        return json.loads(payload)
    except Exception:
        pass

    start = payload.find("{")
    end = payload.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AnthropicResponseError("Claude did not return a valid JSON object")
    try:
        return json.loads(payload[start : end + 1])
    except Exception as exc:
        raise AnthropicResponseError("Claude JSON payload could not be parsed") from exc


def _require_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise AnthropicConfigError("ANTHROPIC_API_KEY is not configured")
    return api_key


def _candidate_models() -> list[str]:
    models = []
    for model in [ANTHROPIC_MODEL, *ANTHROPIC_FALLBACK_MODELS]:
        clean = (model or "").strip()
        if clean and clean not in models:
            models.append(clean)
    return models


def _call_anthropic(
    *,
    system_prompt: str,
    user_payload: dict[str, Any] | str,
    max_tokens: int,
    temperature: float,
) -> str:
    api_key = _require_api_key()
    user_prompt = user_payload if isinstance(user_payload, str) else json.dumps(user_payload, ensure_ascii=False)
    last_error = None

    for model_name in _candidate_models():
        response = None
        for attempt in range(3):
            try:
                response = requests.post(
                    ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": ANTHROPIC_VERSION,
                        "content-type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "system": system_prompt,
                        "messages": [
                            {
                                "role": "user",
                                "content": user_prompt,
                            }
                        ],
                    },
                    timeout=ANTHROPIC_TIMEOUT_SECONDS,
                )
            except requests.RequestException as error:
                last_error = AnthropicResponseError(f"Anthropic request failed: {error}")
                if attempt < 2:
                    time.sleep(1 + attempt)
                    continue
                break

            if response.ok:
                payload = response.json()
                content = payload.get("content") or []
                text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
                if not text_parts:
                    raise AnthropicResponseError("Anthropic response contained no text content")
                return "\n".join(text_parts)

            last_error = AnthropicResponseError(f"Anthropic API error: {response.status_code} {response.text[:200]}")
            if response.status_code in {429, 500, 502, 503, 504, 529} and attempt < 2:
                time.sleep(1 + attempt)
                continue
            break

        if response is not None and response.status_code == 404 and "model" in response.text.lower():
            continue
        raise last_error

    raise last_error or AnthropicResponseError("Anthropic API error: no working model configured")


def generate_cv_copy(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "Tu agis desormais en tant qu'Expert en Recrutement de haut niveau (Headhunter) et Specialiste certifie en optimisation ATS.\n"
        "Ta mission est de rediger un CV de calibre Elite a partir des faits fournis.\n"
        "Tu dois rewriter fortement la formulation: pas de copier-coller plat du texte source.\n\n"
        "## Directives de redaction\n"
        "1. Methode Impact & Data\n"
        "- Transforme chaque mission en realisation claire, credible et orientee impact.\n"
        "- Utilise la logique STAR en version concise: contexte, action, resultat.\n"
        "- Si un chiffre exact est absent, n'invente pas de metrique. Exprime un impact qualitatif fort et professionnel.\n"
        "- Chaque bullet doit sonner comme une preuve de niveau, pas comme une simple tache executee.\n\n"
        "2. Optimisation ATS & mots-cles\n"
        "- Integre naturellement les mots-cles du poste cible et du secteur.\n"
        "- Utilise des synonymes professionnels pour eviter les repetitions.\n"
        "- Priorise les termes les plus credibles par rapport aux faits autorises.\n"
        "- Pour skills_priority: retourne TOUS les skills du profil qui sont pertinents pour le poste, pas seulement le top 3. Vise 10-16 competences.\n\n"
        "3. Golden Header\n"
        "- Redige une accroche de 3 lignes maximum.\n"
        "- Fais ressortir la proposition de valeur, la specialite et le mindset du candidat.\n"
        "- Ton audacieux, net, professionnel, sans cliches.\n\n"
        "4. Structure narrative\n"
        "- Experiences: priorite aux resultats et a la valeur business.\n"
        "- Projets: presentes comme preuves d'execution, de conception, de pilotage ou d'entrepreneuriat.\n"
        "- Competences hybrides: fais ressortir les doubles competences qui differencient le profil.\n"
        "- Si certains elements montrent autonomie, resilience, leadership ou capacite a convaincre, revalorise-les sans inventer.\n\n"
        "## Style impose\n"
        "- Evite 'responsable de', 'charge de', 'j'ai fait'.\n"
        "- Prefere 'Pilotage de...', 'Conception et deploiement de...', 'Structuration de...', 'Industrialisation de...', 'Optimisation de...'.\n"
        "- Le rendu doit etre plus fort, plus recruteur, plus incisif que le texte source.\n\n"
        "## Regles strictes\n"
        "- N'invente jamais employeurs, projets, chiffres, dates, diplomes, certifications, outils, technologies ou resultats.\n"
        "- Ne fusionne pas deux experiences differentes.\n"
        "- Preserve exactement les noms d'entreprise, d'ecole, d'outils et les dates.\n"
        "- Si une information manque, simplifie au lieu d'imaginer.\n"
        "- Ecris dans la langue de l'offre.\n\n"
        "## Output format\n"
        "Return JSON ONLY with this exact shape:\n"
        "{\n"
        '  "headline": "string",\n'
        '  "summary": "string",\n'
        '  "skills_priority": ["string"],\n'
        '  "experience_rewrites": [{"id": "string", "bullets": ["string"]}],\n'
        '  "project_rewrites": [{"id": "string", "bullets": ["string"]}],\n'
        '  "education_rewrites": [{"id": "string", "bullet": "string"}],\n'
        '  "design_notes": ["string"],\n'
        '  "compliance_notes": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=3000,
        temperature=0.3,
    )
    return _extract_json_block(text)


def analyze_job_posting(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "Tu es la premiere IA d'un pipeline de generation de CV.\n"
        "Ta mission est d'analyser une offre d'emploi en profondeur avant toute selection de contenu candidat.\n"
        "Appuie-toi uniquement sur les informations fournies.\n"
        "N'invente pas d'exigences, de stack, de missions ou de contexte entreprise absents.\n\n"
        "Tu dois identifier:\n"
        "- ce que le poste demande vraiment,\n"
        "- les mots-cles prioritaires,\n"
        "- les competences must-have,\n"
        "- les missions probables,\n"
        "- l'angle de positionnement CV a adopter.\n\n"
        "Return JSON ONLY with this exact shape:\n"
        "{\n"
        '  "role_summary": "string",\n'
        '  "priority_keywords": ["string"],\n'
        '  "must_have_skills": ["string"],\n'
        '  "nice_to_have_skills": ["string"],\n'
        '  "core_missions": ["string"],\n'
        '  "candidate_angle": "string",\n'
        '  "language": "string",\n'
        '  "seniority_hint": "string",\n'
        '  "selection_focus": ["string"],\n'
        '  "risks": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=1200,
        temperature=0.2,
    )
    return _extract_json_block(text)


def select_cv_evidence(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "Tu es la deuxieme IA d'un pipeline de generation de CV.\n"
        "Tu recois l'analyse du poste et le profil candidat structure.\n"
        "Ta mission est de choisir les experiences, projets, formations et competences les plus pertinentes pour CE poste.\n"
        "Ne choisis pas tout. Priorise ce qui raconte le meilleur angle candidat pour l'offre.\n"
        "Ne modifie aucun fait. Ne cree aucun id.\n\n"
        "Return JSON ONLY with this exact shape:\n"
        "{\n"
        '  "experience_ids": ["string"],\n'
        '  "project_ids": ["string"],\n'
        '  "education_ids": ["string"],\n'
        '  "skill_names": ["string"],\n'
        '  "cv_focus": "string",\n'
        '  "selection_notes": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=1200,
        temperature=0.2,
    )
    return _extract_json_block(text)


def extract_cv_profile_from_text(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are a strict resume parser.\n"
        "Extract a structured candidate profile from preparsed resume content.\n"
        "The input already contains a local pre-parser output. Use that parsed structure first.\n"
        "Use the document_excerpt only to resolve ambiguities or fill fields the pre-parser clearly exposed.\n"
        "Do not reconstruct the whole CV from scratch from raw text.\n"
        "Use only facts that are explicitly present in the parsed content or excerpt.\n"
        "Do not infer missing dates, technologies, schools, employers, levels, locations, or outcomes.\n"
        "If a field is missing, return an empty string or empty array.\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  "full_name": "string",\n'
        '  "headline": "string",\n'
        '  "email": "string",\n'
        '  "phone": "string",\n'
        '  "location": "string",\n'
        '  "website": "string",\n'
        '  "linkedin": "string",\n'
        '  "github": "string",\n'
        '  "summary": "string",\n'
        '  "target_roles": ["string"],\n'
        '  "skills": ["string"],\n'
        '  "languages": ["string"],\n'
        '  "certifications": ["string"],\n'
        '  "education": [{"school": "string", "degree": "string", "field": "string", "location": "string", "start_date": "string", "end_date": "string", "summary": "string", "highlights": ["string"], "skills": ["string"]}],\n'
        '  "experience": [{"company": "string", "title": "string", "location": "string", "start_date": "string", "end_date": "string", "summary": "string", "highlights": ["string"], "skills": ["string"]}],\n'
        '  "projects": [{"name": "string", "role": "string", "url": "string", "summary": "string", "highlights": ["string"], "technologies": ["string"]}],\n'
        '  "notes": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=2200,
        temperature=0.1,
    )
    return _extract_json_block(text)


def generate_cover_letter(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are an elite career coach writing high-impact cover letters for top students.\n"
        "Write in the same language as the job description (French if French posting).\n\n"
        "## Principles\n"
        "- Open with a hook — a specific, concrete reason why this candidate fits THIS company.\n"
        "- Body: 2-3 tight paragraphs linking candidate's strongest experiences to the role's key challenges.\n"
        "- Use active verbs and concrete examples — avoid generic phrases like 'motivated by challenges'.\n"
        "- Close with confidence, not desperation. A clear call to action.\n"
        "- Total length: 250-320 words maximum. Recruiters skim — every sentence must earn its place.\n\n"
        "## Strict rules\n"
        "- Use only facts present in candidate_basics, allowed_facts, and target.\n"
        "- Do not invent metrics, dates, achievements, or responsibilities.\n"
        "- Keep tone professional but authentic — the candidate should sound like a real person.\n\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  "subject": "string",\n'
        '  "letter_text": "string",\n'
        '  "compliance_notes": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=1600,
        temperature=0.2,
    )
    return _extract_json_block(text)


def generate_application_prep_copy(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are a pragmatic interview coach and recruiting strategist.\n"
        "You receive a job-specific application prep dossier already built from deterministic backend logic.\n"
        "Your role is to sharpen phrasing, not invent substance.\n\n"
        "## Rules\n"
        "- Use only facts present in the provided payload.\n"
        "- Do not invent employers, dates, metrics, tools, project details, or outcomes.\n"
        "- Keep interview questions specific to the target role and company context.\n"
        "- Keep STAR guidance focused on what the candidate personally did.\n"
        "- Keep strengthening actions concrete and short.\n\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  "copy_notes": ["string"],\n'
        '  "interview_questions": {\n'
        '    "motivation_questions": [{"question": "string", "why_asked": "string", "answer_shape": "string"}],\n'
        '    "behavioural_questions": [{"question": "string", "why_asked": "string", "answer_shape": "string"}],\n'
        '    "technical_questions": [{"question": "string", "why_asked": "string", "answer_shape": "string"}]\n'
        "  },\n"
        '  "star_stories": [{"title": "string", "prompt": "string", "when_to_use": "string"}],\n'
        '  "portfolio_ideas": [{"title": "string", "brief": "string", "why_it_helps": "string"}],\n'
        '  "strengthening_actions": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=1800,
        temperature=0.2,
    )
    return _extract_json_block(text)


def summarize_role_description(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are a concise recruiting analyst.\n"
        "Summarize a job posting using only the supplied facts.\n"
        "Do not invent company context, responsibilities, technologies, or requirements.\n"
        "Write for a student candidate who wants a fast understanding of the role.\n"
        "Keep the summary to 2 or 3 sentences maximum.\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  "summary": "string",\n'
        '  "highlights": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=600,
        temperature=0.2,
    )
    return _extract_json_block(text)


def extract_portfolio_snapshot(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are a strict portfolio parser.\n"
        "You receive rendered pages from a personal portfolio website.\n"
        "Use only facts explicitly visible in the provided pages.\n"
        "Prefer concrete project and case-study details over navigation labels or generic marketing copy.\n"
        "Do not invent names, technologies, employers, schools, dates, links, metrics, or outcomes.\n"
        "If a field is missing or uncertain, return an empty string or empty array.\n"
        "Keep project summaries concise and factual.\n"
        "Only include projects that have enough visible detail to be useful.\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  "person_name": "string",\n'
        '  "page_title": "string",\n'
        '  "meta_description": "string",\n'
        '  "narrative": "string",\n'
        '  "skills": ["string"],\n'
        '  "headings": ["string"],\n'
        '  "links": {"github": "string", "linkedin": "string", "email": "string"},\n'
        '  "projects": [{"name": "string", "role": "string", "url": "string", "summary": "string", "highlights": ["string"], "technologies": ["string"], "featured": true}],\n'
        '  "experience": [{"company": "string", "title": "string", "location": "string", "start_date": "string", "end_date": "string", "summary": "string", "highlights": ["string"], "skills": ["string"]}],\n'
        '  "education": [{"school": "string", "degree": "string", "field": "string", "summary": "string"}],\n'
        '  "notes": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=2400,
        temperature=0.1,
    )
    return _extract_json_block(text)
