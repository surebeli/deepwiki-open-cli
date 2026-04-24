from __future__ import annotations

from typing import AsyncIterator

from deepwiki.providers.base import (
    BaseLLMProvider,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)


class LiteLLMProvider(BaseLLMProvider):
    @staticmethod
    def _resolve_model(provider: str, model: str) -> str:
        if "/" in model:
            return model
        return f"{provider}/{model}"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        from litellm import acompletion

        kwargs = {}
        if request.provider == "ollama":
            kwargs["api_base"] = "http://localhost:11434"

        response = await acompletion(
            model=self._resolve_model(request.provider, request.model),
            messages=[{"role": "user", "content": request.prompt}],
            stream=False,
            **kwargs,
        )
        content = response.choices[0].message.content or ""
        return CompletionResponse(content=content, model=request.model, provider=request.provider)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        from litellm import acompletion
        import os

        kwargs = {}
        if request.provider == "ollama":
            kwargs["api_base"] = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        stream = await acompletion(
            model=self._resolve_model(request.provider, request.model),
            messages=[{"role": "user", "content": request.prompt}],
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        from litellm import aembedding
        import os

        kwargs = {}
        if request.provider == "ollama":
            kwargs["api_base"] = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        try:
            # Try batch embedding first
            response = await aembedding(
                model=self._resolve_model(request.provider, request.model),
                input=request.texts,
                **kwargs,
            )
            embeddings = [item["embedding"] for item in response["data"]]
            return EmbeddingResponse(embeddings=embeddings, model=request.model, provider=request.provider)
        except Exception as batch_error:
            # Fallback to individual embedding if batch fails
            if len(request.texts) > 1:
                embeddings = []
                for idx, text in enumerate(request.texts):
                    try:
                        resp = await aembedding(
                            model=self._resolve_model(request.provider, request.model),
                            input=[text],
                            **kwargs,
                        )
                        embeddings.append(resp["data"][0]["embedding"])
                    except Exception as single_error:
                        print(f"Individual embedding failed for text at index {idx} (len={len(text)}): {single_error}")
                        # Provide a zero vector as fallback for the single failed chunk to keep indices aligned
                        # nomic-embed-text has 768 dimensions
                        embeddings.append([0.0] * 768) 
                return EmbeddingResponse(embeddings=embeddings, model=request.model, provider=request.provider)
            
            # If it was already a single text or we can't recover
            print(f"Embedding failed: {batch_error}")
            print(f"Model: {self._resolve_model(request.provider, request.model)}")
            raise batch_error
