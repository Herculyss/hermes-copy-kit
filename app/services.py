import json
import os
from typing import Any

import httpx

from app.schemas import ScriptSections

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
APP_NAME = "hermes-copy-kit"


def _build_http_client():
    return httpx.Client(timeout=60.0)


def _get_api_key():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return api_key


def _extract_message_content(response_json):
    try:
        return response_json["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Invalid response from OpenRouter") from exc


def _call_openrouter(system_prompt, user_prompt):
    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": APP_NAME,
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
    }
    with _build_http_client() as client:
        response = client.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        return _extract_message_content(response.json())


def generate_copy_variations(product_name, description, audience):
    system_prompt = (
        "You are a direct response copywriter. "
        "Return only valid JSON as an array with exactly 5 strings. "
        "Each string must be a ready-to-use marketing copy variation. "
        "Do not include markdown, numbering, or extra text."
    )
    user_prompt = (
        f"Product name: {product_name}\n"
        f"Description: {description}\n"
        f"Audience: {audience}\n\n"
        "Write 5 distinct copy variations in English. "
        "Make them concise, persuasive, and usable in ads or landing pages."
    )
    content = _call_openrouter(system_prompt, user_prompt)
    try:
        variations = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenRouter did not return valid JSON") from exc
    if not isinstance(variations, list) or len(variations) != 5:
        raise RuntimeError("Did not return exactly 5 variations")
    return [item.strip() for item in variations]


def generate_video_script(product_name, description, style):
    system_prompt = (
        "You are a video ad scriptwriter. "
        "Return only valid JSON with keys: hook, problem, solution, cta. "
        "Do not include markdown or extra commentary."
    )
    user_prompt = (
        f"Product name: {product_name}\n"
        f"Description: {description}\n"
        f"Style: {style}\n\n"
        "Write a 30-second video script in English using the "
        "Hook-Problem-Solution-CTA structure."
    )
    content = _call_openrouter(system_prompt, user_prompt)
    try:
        raw_script = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenRouter did not return valid JSON") from exc
    return ScriptSections(**raw_script)
