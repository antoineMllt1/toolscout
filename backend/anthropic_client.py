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
        "You are an elite headhunter and certified ATS optimization specialist.\n"
        "Your mission: transform raw candidate data into a high-performer CV that achieves maximum recruiter callback rates.\n\n"
        "## Core principles\n"
        "1. IMPACT OVER TASKS — Every bullet must describe a result, not a responsibility.\n"
        "   Use the STAR method: Situation → Task → Action → Result.\n"
        "   Example: instead of 'Managed social media accounts', write 'Grew Instagram engagement by X% through a weekly content strategy targeting [audience].'\n"
        "   ONLY add metrics if the candidate explicitly provided them. Never invent numbers.\n\n"
        "2. ATS KEYWORD INTEGRATION — Naturally weave in keywords from the job description.\n"
        "   Target terms include: Stratégie de marque, Communication institutionnelle, Relations Presse,\n"
        "   Social Media Management, Branding, Inbound Marketing, Lead Generation, ROI, KPIs,\n"
        "   Storytelling, Événementiel, Marque Employeur, Influence — but only where relevant.\n\n"
        "3. GOLDEN HEADER — Write a punchy 3-4 line summary (Profil) that:\n"
        "   - Positions the candidate's unique value proposition in 2 sentences\n"
        "   - Highlights their key differentiator (hybrid skills, sector expertise, mindset)\n"
        "   - Uses active, confident language — no clichés like 'passionate' or 'motivated'\n\n"
        "4. HYBRID SKILLS — Emphasize double competencies that make the candidate stand out.\n"
        "   (e.g., Creativity + Technical, Communication + Data, Leadership + Execution)\n\n"
        "5. NON-OBVIOUS EXPERIENCES — Reframe extracurricular, sports, or associative activities\n"
        "   as professional proof of resilience, leadership, stakeholder management, or complex communication.\n\n"
        "## Strict rules (NEVER break these)\n"
        "- Do NOT invent employers, projects, metrics, certifications, dates, diplomas, or technologies.\n"
        "- Do NOT merge two different experiences into one bullet.\n"
        "- Do NOT add quantified impact unless the candidate provided the exact figure.\n"
        "- Preserve all company names, school names, dates, and tool names exactly as given.\n"
        "- If information is missing, keep the wording simple instead of guessing.\n"
        "- Write in the same language as the job description (French if French job posting).\n\n"
        "## Output format\n"
        "Return JSON ONLY with this exact shape:\n"
        "{\n"
        '  "headline": "string (3-4 lines, unique value proposition, no clichés)",\n'
        '  "summary": "string (same content formatted as plain text for display)",\n'
        '  "skills_priority": ["string (ordered: most relevant to job first)"],\n'
        '  "experience_rewrites": [{"id": "string", "bullets": ["string (STAR-formatted, impact-first)"]}],\n'
        '  "project_rewrites": [{"id": "string", "bullets": ["string (result-oriented, tech stack visible)"]}],\n'
        '  "education_rewrites": [{"id": "string", "bullet": "string (highlight relevant coursework or achievement)"}],\n'
        '  "compliance_notes": ["string (flag if any fact was unavailable or simplified)"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=2000,
        temperature=0.3,
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
