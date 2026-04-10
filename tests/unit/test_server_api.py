from __future__ import annotations

from fastapi.testclient import TestClient

from deepwiki.server import api
from deepwiki.config.settings import Settings
from deepwiki.core.models import AnswerSource, AskResult


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


def test_generate_and_research_redact_repo_path(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(api, "resolve_repo_path", lambda *args, **kwargs: repo)
    monkeypatch.setattr(api, "read_repo_files", lambda *args, **kwargs: [("a.py", "print('x')")])
    monkeypatch.setattr(
        api,
        "build_runtime",
        lambda **kwargs: (
            Settings("openai", "m", "openai", "e", 3, 100, 10, str(tmp_path / ".cache")),
            object(),
        ),
    )

    class _Engine:
        def __init__(self, provider) -> None:
            pass

        async def answer(self, **kwargs):
            return AskResult(
                answer="answer",
                sources=[AnswerSource(file_path="a.py", chunk_preview="x", relevance_score=0.9)],
                metadata={"repo": "repo", "index_cached": False},
            )

    monkeypatch.setattr(api, "RAGEngine", _Engine)
    app = api.create_app()
    client = TestClient(app)

    generate = client.post("/api/generate", json={"repo": str(repo), "offline": True})
    assert generate.status_code == 200
    assert generate.json()["metadata"]["repo"] == "repo"

    research = client.post("/api/research", json={"repo": str(repo), "topic": "safety", "iterations": 1})
    assert research.status_code == 200
    assert research.json()["metadata"]["repo"] == "repo"
