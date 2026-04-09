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

        response = await acompletion(
            model=self._resolve_model(request.provider, request.model),
            messages=[{"role": "user", "content": request.prompt}],
            stream=False,
        )
        content = response.choices[0].message.content or ""
        return CompletionResponse(content=content, model=request.model, provider=request.provider)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        from litellm import acompletion

        stream = await acompletion(
            model=self._resolve_model(request.provider, request.model),
            messages=[{"role": "user", "content": request.prompt}],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        from litellm import aembedding

        response = await aembedding(
            model=self._resolve_model(request.provider, request.model),
            input=request.texts,
        )
        embeddings = [item["embedding"] for item in response["data"]]
        return EmbeddingResponse(embeddings=embeddings, model=request.model, provider=request.provider)
