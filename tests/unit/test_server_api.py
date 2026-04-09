from __future__ import annotations

from fastapi.testclient import TestClient

from deepwiki.server import api


def test_health_and_providers_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "load_provider_catalogs",
        lambda: ({"openai": ["gpt-4o-mini"]}, {"openai": ["text-embedding-3-small"]}),
    )
    app = api.create_app()
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["type"] == "health"

    providers = client.get("/api/providers")
    assert providers.status_code == 200
    assert providers.json()["data"]["generator"]["openai"] == ["gpt-4o-mini"]

    models = client.get("/api/models/openai")
    assert models.status_code == 200
    assert models.json()["data"]["models"] == ["gpt-4o-mini"]


def test_generate_requires_repo_or_repo_url() -> None:
    app = api.create_app()
    client = TestClient(app)

    response = client.post("/api/generate", json={"offline": True})
    assert response.status_code == 400
    assert "repo or repo_url is required" in response.json()["detail"]
