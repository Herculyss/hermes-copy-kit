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

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post("/generate-copy", json=payload)

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

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "style": "direto e energético",
    }

    response = client.post("/generate-script", json=payload)

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

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post("/generate-copy", json=payload)

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

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post("/generate-copy", json=payload)

    assert response.status_code == 200
    assert seen_urls == [
        "https://openrouter.ai/api/v1/chat/completions",
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    ]


def test_logs_obsidian_alert_when_failure_rate_exceeds_half(monkeypatch) -> None:
    notes = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    def fake_append(message: str) -> None:
        notes.append(message)

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
    monkeypatch.setattr("app.services._request_stats", {"total": 0, "failed": 0, "alerted": False})

    payload = {
        "product_name": "FocusFlow",
        "description": "Uma app que organiza tarefas e reduz distrações.",
        "audience": "freelancers ocupados",
    }

    response = client.post("/generate-copy", json=payload)

    assert response.status_code == 502
    assert notes == ["Free tiers sob pressão. Considerar adicionar créditos."]
