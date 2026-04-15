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
