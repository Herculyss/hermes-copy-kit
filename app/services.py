import json
import os
import time
from datetime import datetime
from typing import Any, List, Optional

import httpx

from app.schemas import ScriptSections

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
GOOGLE_AI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GOOGLE_AI_MODEL = "gemini-2.0-flash"
FREE_MODEL_CACHE_TTL_SECONDS = 3600
APP_NAME = "CopySnap"
CAPACITY_ALERT_MESSAGE = "Free tiers sob pressão. Considerar adicionar créditos."
DAILY_LOG_DIR = os.path.expanduser("~/hermes-vault/00-DASHBOARD/Daily-Log")
DISCORD_WEBHOOKS_FILE = os.path.expanduser("~/hermes-project/discord_webhooks.json")
DISCORD_ALERTS_WEBHOOK_ENV = "DISCORD_ALERTS_WEBHOOK_URL"

_free_models_cache: Optional[List[str]] = None
_free_models_cache_expires_at = 0.0
_request_stats = {"total": 0, "failed": 0, "alerted": False}


def _build_http_client() -> httpx.Client:
    return httpx.Client(timeout=60.0)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def _extract_message_content(response_json: dict[str, Any]) -> str:
    try:
        return response_json["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Invalid response payload from model provider") from exc


def _is_zero_price(value: Any) -> bool:
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def _get_openrouter_free_models(client: httpx.Client) -> list[str]:
    global _free_models_cache, _free_models_cache_expires_at

    now = time.time()
    if _free_models_cache and now < _free_models_cache_expires_at:
        return _free_models_cache

    api_key = _get_required_env("OPENROUTER_API_KEY")
    response = client.get(
        OPENROUTER_MODELS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": APP_NAME,
        },
    )
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data", [])
    models: list[str] = []
    for item in data:
        pricing = item.get("pricing", {})
        if _is_zero_price(pricing.get("prompt")) and _is_zero_price(pricing.get("completion")):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.strip())

    if not models:
        raise RuntimeError("No free OpenRouter models available")

    _free_models_cache = models
    _free_models_cache_expires_at = now + FREE_MODEL_CACHE_TTL_SECONDS
    return models


def _call_openrouter_free_models(client: httpx.Client, system_prompt: str, user_prompt: str) -> str:
    api_key = _get_required_env("OPENROUTER_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": APP_NAME,
    }

    last_error: Optional[Exception] = None
    for model in _get_openrouter_free_models(client):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
        }
        response = client.post(OPENROUTER_URL, headers=headers, json=payload)
        if response.status_code == 429:
            last_error = RuntimeError(f"Rate limited on OpenRouter model: {model}")
            continue
        response.raise_for_status()
        return _extract_message_content(response.json())

    if last_error:
        raise last_error
    raise RuntimeError("OpenRouter free models were unavailable")


def _call_google_ai_studio(client: httpx.Client, system_prompt: str, user_prompt: str) -> str:
    api_key = _get_required_env("GOOGLE_AI_KEY")
    response = client.post(
        GOOGLE_AI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GOOGLE_AI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
        },
    )
    response.raise_for_status()
    return _extract_message_content(response.json())


def _append_capacity_alert_to_daily_log(message: str) -> None:
    os.makedirs(DAILY_LOG_DIR, exist_ok=True)
    daily_log_path = os.path.join(DAILY_LOG_DIR, f"{datetime.now():%Y-%m-%d}.md")
    prefix = "\n" if os.path.exists(daily_log_path) and os.path.getsize(daily_log_path) > 0 else ""
    with open(daily_log_path, "a", encoding="utf-8") as daily_log:
        daily_log.write(f"{prefix}{message}\n")


def _get_alerts_webhook_url() -> Optional[str]:
    env_webhook = os.getenv(DISCORD_ALERTS_WEBHOOK_ENV)
    if env_webhook:
        return env_webhook

    if not os.path.exists(DISCORD_WEBHOOKS_FILE):
        return None

    with open(DISCORD_WEBHOOKS_FILE, "r", encoding="utf-8") as webhooks_file:
        payload = json.load(webhooks_file)

    return payload.get("webhooks", {}).get("alerts", {}).get("webhook_url")


def _send_discord_alert(message: str) -> None:
    webhook_url = _get_alerts_webhook_url()
    if not webhook_url:
        return

    with _build_http_client() as client:
        response = client.post(
            webhook_url,
            json={
                "content": f"⚠️ {message}",
                "username": "CopySnap Alerts",
            },
        )
        response.raise_for_status()


def _record_request_result(success: bool) -> None:
    _request_stats["total"] += 1
    if not success:
        _request_stats["failed"] += 1

    failure_rate = _request_stats["failed"] / _request_stats["total"]
    if failure_rate > 0.5 and not _request_stats["alerted"]:
        _append_capacity_alert_to_daily_log(CAPACITY_ALERT_MESSAGE)
        try:
            _send_discord_alert(CAPACITY_ALERT_MESSAGE)
        except Exception:
            pass
        _request_stats["alerted"] = True


def _call_openrouter(system_prompt: str, user_prompt: str) -> str:
    with _build_http_client() as client:
        try:
            try:
                content = _call_openrouter_free_models(client, system_prompt, user_prompt)
            except Exception:
                content = _call_google_ai_studio(client, system_prompt, user_prompt)
            _record_request_result(success=True)
            return content
        except Exception as exc:
            _record_request_result(success=False)
            raise RuntimeError(
                "OpenRouter free models are unavailable and Google AI Studio fallback also failed. Consider adding credits or retry later."
            ) from exc


def generate_copy_variations(product_name: str, description: str, audience: str) -> list[str]:
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


def generate_video_script(product_name: str, description: str, style: str) -> ScriptSections:
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
