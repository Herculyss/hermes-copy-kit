import json

import httpx
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_generate_copy_uses_openrouter_and_returns_five_variations(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-openrouter-key"
        payload = json.loads(request.content.decode())
        assert payload["model"] == "meta-llama/llama-3.3-70b-instruct:free"
        assert "FocusFlow" in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '["Copy 1 FocusFlow", "Copy 2 FocusFlow", "Copy 3 FocusFlow", "Copy 4 FocusFlow", "Copy 5 FocusFlow"]'
                        }
                    }
                ]
            },
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(
        "app.services._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        "app.services._get_openrouter_free_models",
        lambda client: ["meta-llama/llama-3.3-70b-instruct:free"],
    )
    monkeypatch.setattr("app.main._verify_license_key", lambda _: True)

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post(
        "/generate-copy",
        json=payload,
        headers={"x-forwarded-for": "203.0.113.1", "x-license-key": "valid-license"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["product_name"] == "FocusFlow"
    assert len(data["variations"]) == 5
    assert data["variations"][0] == "Copy 1 FocusFlow"


def test_generate_script_uses_openrouter_and_returns_hpsc_sections(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://openrouter.ai/api/v1/chat/completions"
        payload = json.loads(request.content.decode())
        assert payload["model"] == "meta-llama/llama-3.3-70b-instruct:free"
        assert "direto e energético" in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"hook":"Gancho","problem":"Problema","solution":"Solução com FocusFlow","cta":"CTA com FocusFlow"}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(
        "app.services._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        "app.services._get_openrouter_free_models",
        lambda client: ["meta-llama/llama-3.3-70b-instruct:free"],
    )
    monkeypatch.setattr("app.main._verify_license_key", lambda _: True)

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "style": "direto e energético",
    }

    response = client.post(
        "/generate-script",
        json=payload,
        headers={"x-forwarded-for": "203.0.113.2", "x-license-key": "valid-license"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["product_name"] == "FocusFlow"
    assert data["duration_seconds"] == 30
    assert data["style"] == "direto e energético"
    assert data["script"] == {
        "hook": "Gancho",
        "problem": "Problema",
        "solution": "Solução com FocusFlow",
        "cta": "CTA com FocusFlow",
    }


def test_openrouter_fallback_tries_next_free_model_after_429(monkeypatch) -> None:
    seen_models = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        seen_models.append(payload["model"])
        if payload["model"] == "model-a:free":
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '["Fallback copy 1", "Fallback copy 2", "Fallback copy 3", "Fallback copy 4", "Fallback copy 5"]'
                        }
                    }
                ]
            },
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(
        "app.services._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        "app.services._get_openrouter_free_models",
        lambda client: ["model-a:free", "model-b:free"],
    )
    monkeypatch.setattr("app.main._verify_license_key", lambda _: True)

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post(
        "/generate-copy",
        json=payload,
        headers={"x-forwarded-for": "203.0.113.3", "x-license-key": "valid-license"},
    )

    assert response.status_code == 200
    assert seen_models == ["model-a:free", "model-b:free"]


def test_free_model_discovery_filters_zero_pricing_and_uses_cache(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url == "https://openrouter.ai/api/v1/models"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "free-model-1", "pricing": {"prompt": "0", "completion": "0"}},
                    {"id": "paid-model", "pricing": {"prompt": "0.1", "completion": "0.2"}},
                    {"id": "free-model-2", "pricing": {"prompt": 0, "completion": 0}},
                ]
            },
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(
        "app.services._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr("app.services._free_models_cache", None)
    monkeypatch.setattr("app.services._free_models_cache_expires_at", 0)
    monkeypatch.setattr("app.services.time.time", lambda: 1000)

    import app.services as services

    with services._build_http_client() as mock_client:
        first = services._get_openrouter_free_models(mock_client)
        second = services._get_openrouter_free_models(mock_client)

    assert first == ["free-model-1", "free-model-2"]
    assert second == ["free-model-1", "free-model-2"]
    assert calls["count"] == 1


def test_falls_back_to_google_ai_studio_after_openrouter_free_fails(monkeypatch) -> None:
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url) == "https://openrouter.ai/api/v1/chat/completions":
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        assert request.headers["authorization"] == "Bearer google-test-key"
        payload = json.loads(request.content.decode())
        assert payload["model"] == "gemini-2.0-flash"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '["Google fallback 1", "Google fallback 2", "Google fallback 3", "Google fallback 4", "Google fallback 5"]'
                        }
                    }
                ]
            },
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("GOOGLE_AI_KEY", "google-test-key")
    monkeypatch.setattr(
        "app.services._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        "app.services._get_openrouter_free_models",
        lambda client: ["model-a:free"],
    )
    monkeypatch.setattr("app.main._verify_license_key", lambda _: True)

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post(
        "/generate-copy",
        json=payload,
        headers={"x-forwarded-for": "203.0.113.4", "x-license-key": "valid-license"},
    )

    assert response.status_code == 200
    assert seen_urls == [
        "https://openrouter.ai/api/v1/chat/completions",
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    ]


def test_logs_obsidian_and_discord_alert_when_failure_rate_exceeds_half(monkeypatch) -> None:
    notes = []
    discord_alerts = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    def fake_append(message: str) -> None:
        notes.append(message)

    def fake_discord_alert(message: str) -> None:
        discord_alerts.append(message)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.delenv("GOOGLE_AI_KEY", raising=False)
    monkeypatch.setattr(
        "app.services._build_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        "app.services._get_openrouter_free_models",
        lambda client: ["model-a:free"],
    )
    monkeypatch.setattr("app.services._append_capacity_alert_to_daily_log", fake_append)
    monkeypatch.setattr("app.services._send_discord_alert", fake_discord_alert)
    monkeypatch.setattr("app.services._request_stats", {"total": 0, "failed": 0, "alerted": False})
    monkeypatch.setattr("app.main._verify_license_key", lambda _: True)

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post(
        "/generate-copy",
        json=payload,
        headers={"x-forwarded-for": "203.0.113.5", "x-license-key": "valid-license"},
    )

    assert response.status_code == 502
    assert notes == ["Free tiers sob pressão. Considerar adicionar créditos."]
    assert discord_alerts == ["Free tiers sob pressão. Considerar adicionar créditos."]


def test_generate_copy_limits_free_usage_to_one_request_per_day_per_ip(monkeypatch, tmp_path) -> None:
    usage_store = tmp_path / "usage_limits.json"
    monkeypatch.setenv("USAGE_STORE_PATH", str(usage_store))
    monkeypatch.setattr("app.main.generate_copy_variations", lambda **_: ["A", "B", "C", "D", "E"])
    monkeypatch.setattr("app.main._utc_today", lambda: "2026-04-15")
    monkeypatch.setattr("app.main._verify_license_key", lambda _: False)

    payload = {
        "product_name": "CopySnap",
        "description": "Generate ads fast.",
        "audience": "founders",
    }
    headers = {"x-forwarded-for": "203.0.113.10"}

    first = client.post("/generate-copy", json=payload, headers=headers)
    second = client.post("/generate-copy", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {
        "error": "Free limit reached. Get unlimited access.",
        "upgrade_url": "https://fuioherm.gumroad.com/l/copysnap",
    }



def test_generate_copy_resets_limit_on_next_utc_day(monkeypatch, tmp_path) -> None:
    usage_store = tmp_path / "usage_limits.json"
    monkeypatch.setenv("USAGE_STORE_PATH", str(usage_store))
    monkeypatch.setattr("app.main.generate_copy_variations", lambda **_: ["A", "B", "C", "D", "E"])
    current_day = {"value": "2026-04-15"}
    monkeypatch.setattr("app.main._utc_today", lambda: current_day["value"])
    monkeypatch.setattr("app.main._verify_license_key", lambda _: False)

    payload = {
        "product_name": "CopySnap",
        "description": "Generate ads fast.",
        "audience": "founders",
    }
    headers = {"x-forwarded-for": "203.0.113.11"}

    first = client.post("/generate-copy", json=payload, headers=headers)
    second = client.post("/generate-copy", json=payload, headers=headers)
    current_day["value"] = "2026-04-16"
    third = client.post("/generate-copy", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert third.status_code == 200



def test_verify_license_placeholder_returns_invalid(monkeypatch) -> None:
    monkeypatch.setattr("app.main._verify_license_key", lambda key: key == "valid-license")

    invalid = client.post("/verify-license", json={"license_key": "bad-license"})
    valid = client.post("/verify-license", json={"license_key": "valid-license"})

    assert invalid.status_code == 200
    assert invalid.json() == {"valid": False}
    assert valid.status_code == 200
    assert valid.json() == {"valid": True}
