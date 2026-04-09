from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from deepwiki.config.settings import Settings
from deepwiki.core.rag_engine import RAGEngine
from deepwiki.data.vector_store import QueryResult
from deepwiki.providers.base import CompletionResponse, EmbeddingResponse


class DummyProvider:
    def __init__(self) -> None:
        self.last_prompt = ""

    async def complete(self, request):
        self.last_prompt = request.prompt
        return CompletionResponse(content="answer", model=request.model, provider=request.provider)

    async def stream(self, request):
        yield "x"

    async def embed(self, request):
        return EmbeddingResponse(embeddings=[[0.1, 0.2] for _ in request.texts], model=request.model, provider=request.provider)


@dataclass
class DummyStore:
    persisted: bool = False

    def load(self, path: str) -> bool:
        return False

    def clear(self) -> None:
        pass

    def add_documents(self, documents) -> None:
        pass

    def persist(self) -> None:
        self.persisted = True

    def query(self, embedding, top_k: int = 20):
        return [QueryResult(id="1", text="ctx", metadata={"file_path": "a.py", "chunk_index": 0}, relevance_score=0.8)]


def test_answer_top_k_validation() -> None:
    engine = RAGEngine(provider=DummyProvider())
    settings = Settings("openai", "m", "openai", "e", 3, 50, 10, ".cache")
    with pytest.raises(ValueError, match="top_k must be > 0"):
        asyncio.run(engine.answer(Path("."), [("a.py", "x")], "q", settings, top_k=0))


def test_build_index_and_answer_from_index(monkeypatch, tmp_path: Path) -> None:
    engine = RAGEngine(provider=DummyProvider(), embedding_batch_size=2)
    settings = Settings("openai", "m", "openai", "e", 3, 2, 0, str(tmp_path / ".cache"))
    store = DummyStore()

    monkeypatch.setattr(
        "deepwiki.core.rag_engine.split_documents",
        lambda files, chunk_size, chunk_overlap: [
            type("Chunk", (), {"chunk_id": "a.py::0", "file_path": "a.py", "chunk_index": 0, "text": "hello world"})()
        ],
    )

    chunk_count = asyncio.run(engine._build_index(store=store, files=[("a.py", "hello world")], settings=settings))
    assert chunk_count == 1

    result = asyncio.run(
        engine._answer_from_index(
            store=store,
            repo_path=tmp_path,
            question="what?",
            settings=settings,
            top_k=2,
            index_cached=False,
            started=0.0,
        )
    )
    assert result.answer == "answer"
    assert result.metadata["chunks_retrieved"] == 1
    assert result.sources[0].file_path == "a.py"


def test_build_index_empty_chunks_raises(monkeypatch) -> None:
    engine = RAGEngine(provider=DummyProvider())
    settings = Settings("openai", "m", "openai", "e", 3, 2, 0, ".cache")
    store = DummyStore()
    monkeypatch.setattr("deepwiki.core.rag_engine.split_documents", lambda **kwargs: [])
    with pytest.raises(ValueError, match="No readable content available for indexing"):
        asyncio.run(engine._build_index(store=store, files=[("a.py", "")], settings=settings))


def test_answer_from_index_empty_embedding_raises(tmp_path: Path) -> None:
    class EmptyEmbedProvider(DummyProvider):
        async def embed(self, request):
            return EmbeddingResponse(embeddings=[], model=request.model, provider=request.provider)

    engine = RAGEngine(provider=EmptyEmbedProvider())
    settings = Settings("openai", "m", "openai", "e", 3, 2, 0, str(tmp_path / ".cache"))
    with pytest.raises(ValueError, match="empty query embedding"):
        asyncio.run(
            engine._answer_from_index(
                store=DummyStore(),
                repo_path=tmp_path,
                question="q",
                settings=settings,
                top_k=1,
                index_cached=True,
                started=0.0,
            )
        )


def test_answer_from_index_without_retrieved_context(tmp_path: Path) -> None:
    class EmptyStore(DummyStore):
        def query(self, embedding, top_k: int = 20):
            return []

    provider = DummyProvider()
    engine = RAGEngine(provider=provider)
    settings = Settings("openai", "m", "openai", "e", 3, 2, 0, str(tmp_path / ".cache"))

    result = asyncio.run(
        engine._answer_from_index(
            store=EmptyStore(),
            repo_path=tmp_path,
            question="q",
            settings=settings,
            top_k=1,
            index_cached=False,
            started=0.0,
        )
    )
    assert result.answer == "answer"
    assert result.sources == []
    assert "(no relevant context found)" in provider.last_prompt
