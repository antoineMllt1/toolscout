import json
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


ANTHROPIC_API_URL = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_TIMEOUT_SECONDS = int(os.environ.get("ANTHROPIC_TIMEOUT_SECONDS", "45"))
ANTHROPIC_FALLBACK_MODELS = [
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
    "claude-sonnet-4-20250514",
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
        "You are a strict CV copywriting assistant.\n"
        "Follow every rule in strict_rules.\n"
        "Use only the facts inside allowed_facts and target.\n"
        "Never invent metrics, dates, tools, companies, degrees, or outcomes.\n"
        "Return JSON only, with this exact shape:\n"
        "{\n"
        '  "headline": "string",\n'
        '  "summary": "string",\n'
        '  "skills_priority": ["string"],\n'
        '  "experience_rewrites": [{"id": "string", "bullets": ["string"]}],\n'
        '  "project_rewrites": [{"id": "string", "bullets": ["string"]}],\n'
        '  "education_rewrites": [{"id": "string", "bullet": "string"}],\n'
        '  "compliance_notes": ["string"]\n'
        "}"
    )
    text = _call_anthropic(
        system_prompt=system_prompt,
        user_payload=prompt_payload,
        max_tokens=1400,
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
        "You are a strict cover letter assistant.\n"
        "Follow every rule in strict_rules.\n"
        "Use only the facts in candidate_basics, allowed_facts, and target.\n"
        "Do not invent metrics, responsibilities, dates, achievements, or motivation details.\n"
        "Keep the tone professional and concise for a French student or early-career application.\n"
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
