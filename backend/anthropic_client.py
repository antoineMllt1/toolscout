import json
import os
from typing import Any

import requests


ANTHROPIC_API_URL = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_TIMEOUT_SECONDS = int(os.environ.get("ANTHROPIC_TIMEOUT_SECONDS", "45"))


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


def generate_cv_copy(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise AnthropicConfigError("ANTHROPIC_API_KEY is not configured")

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

    user_prompt = json.dumps(prompt_payload, ensure_ascii=False)
    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 1400,
            "temperature": 0.2,
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

    if not response.ok:
        raise AnthropicResponseError(f"Anthropic API error: {response.status_code} {response.text[:200]}")

    payload = response.json()
    content = payload.get("content") or []
    text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
    if not text_parts:
        raise AnthropicResponseError("Anthropic response contained no text content")
    return _extract_json_block("\n".join(text_parts))
