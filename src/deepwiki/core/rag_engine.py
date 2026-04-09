from __future__ import annotations

import time
from pathlib import Path

from deepwiki.config.settings import Settings
from deepwiki.core.models import AnswerSource, AskResult
from deepwiki.data.cache_manager import CacheManager
from deepwiki.data.text_splitter import split_documents
from deepwiki.data.vector_store import ChromaVectorStore, VectorDocument
from deepwiki.providers.base import BaseLLMProvider, CompletionRequest, EmbeddingRequest


class RAGEngine:
    def __init__(self, provider: BaseLLMProvider, embedding_batch_size: int = 500):
        self.provider = provider
        self.embedding_batch_size = embedding_batch_size

    async def answer(
        self,
        repo_path: Path,
        files: list[tuple[str, str]],
        question: str,
        settings: Settings,
        top_k: int | None = None,
        use_cache: bool = True,
    ) -> AskResult:
        started = time.perf_counter()
        effective_top_k = top_k if top_k is not None else settings.top_k
        if effective_top_k <= 0:
            raise ValueError("top_k must be > 0")

        cache_manager = CacheManager(settings.cache_dir)
        cache_key = cache_manager.build_cache_key(
            repo_path=repo_path,
            files=files,
            embed_provider=settings.embed_provider,
            embed_model=settings.embed_model,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        index_path = cache_manager.index_path(cache_key)
        store = ChromaVectorStore(str(index_path))

        index_cached = False
        if use_cache:
            index_cached = cache_manager.is_cache_hit(
                cache_key=cache_key,
                repo_path=repo_path,
                files=files,
                embed_provider=settings.embed_provider,
                embed_model=settings.embed_model,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            ) and store.load(str(index_path))

        if not index_cached:
            chunk_count = await self._build_index(store=store, files=files, settings=settings)
            store.persist()
            if use_cache:
                cache_manager.save_metadata(
                    cache_key=cache_key,
                    repo_path=repo_path,
                    files=files,
                    embed_provider=settings.embed_provider,
                    embed_model=settings.embed_model,
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                    chunk_count=chunk_count,
                )

        return await self._answer_from_index(
            store=store,
            repo_path=repo_path,
            question=question,
            settings=settings,
            top_k=effective_top_k,
            index_cached=index_cached,
            started=started,
        )

    async def _build_index(
        self,
        store: ChromaVectorStore,
        files: list[tuple[str, str]],
        settings: Settings,
    ) -> int:
        chunks = split_documents(
            files=files,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        if not chunks:
            raise ValueError("No readable content available for indexing")

        store.clear()
        for offset in range(0, len(chunks), self.embedding_batch_size):
            batch = chunks[offset : offset + self.embedding_batch_size]
            embedding_response = await self.provider.embed(
                EmbeddingRequest(
                    texts=[chunk.text for chunk in batch],
                    model=settings.embed_model,
                    provider=settings.embed_provider,
                )
            )
            documents = [
                VectorDocument(
                    id=chunk.chunk_id,
                    text=chunk.text,
                    embedding=embedding_response.embeddings[idx],
                    metadata={
                        "file_path": chunk.file_path,
                        "chunk_index": chunk.chunk_index,
                    },
                )
                for idx, chunk in enumerate(batch)
            ]
            store.add_documents(documents)

        return len(chunks)

    async def _answer_from_index(
        self,
        store: ChromaVectorStore,
        repo_path: Path,
        question: str,
        settings: Settings,
        top_k: int,
        index_cached: bool,
        started: float,
    ) -> AskResult:
        question_embedding = await self.provider.embed(
            EmbeddingRequest(
                texts=[question],
                model=settings.embed_model,
                provider=settings.embed_provider,
            )
        )
        if not question_embedding.embeddings:
            raise ValueError("Embedding provider returned empty query embedding")

        retrieved = store.query(embedding=question_embedding.embeddings[0], top_k=top_k)
        context_blocks: list[str] = []
        sources: list[AnswerSource] = []

        for result in retrieved:
            file_path = str(result.metadata.get("file_path", "unknown"))
            chunk_index = result.metadata.get("chunk_index", "?")
            context_blocks.append(f"[{file_path}::{chunk_index}]\n{result.text}")
            sources.append(
                AnswerSource(
                    file_path=file_path,
                    chunk_preview=result.text[:200],
                    relevance_score=result.relevance_score,
                )
            )

        context_text = "\n\n".join(context_blocks) if context_blocks else "(no relevant context found)"
        prompt = (
            "You are a technical assistant for repository Q&A. "
            "Answer based on the provided context. If context is insufficient, say so clearly.\n\n"
            f"Question:\n{question}\n\n"
            f"Context:\n{context_text}\n\n"
            "Answer in markdown."
        )

        completion = await self.provider.complete(
            CompletionRequest(
                prompt=prompt,
                model=settings.model,
                provider=settings.provider,
                stream=False,
            )
        )

        metadata = {
            "repo": str(repo_path.resolve()),
            "question": question,
            "provider": settings.provider,
            "model": settings.model,
            "top_k": top_k,
            "chunks_retrieved": len(retrieved),
            "index_cached": index_cached,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

        return AskResult(answer=completion.content, sources=sources, metadata=metadata)
