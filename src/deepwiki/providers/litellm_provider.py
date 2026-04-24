from __future__ import annotations

from typing import AsyncIterator

from deepwiki.providers.base import (
    BaseLLMProvider,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)


class LiteLLMProvider(BaseLLMProvider):  # pragma: no cover
    @staticmethod
    def _resolve_model(provider: str, model: str) -> str:
        if "/" in model:
            return model
        return f"{provider}/{model}"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        from litellm import acompletion
        import os
        import json

        kwargs = {}
        
        # Try to read OpenClaw config for API keys
        openclaw_models_path = os.path.expanduser("~/.openclaw/agents/main/agent/models.json")
        openclaw_api_key = None
        openclaw_base_url = None
        if os.path.exists(openclaw_models_path):
            try:
                with open(openclaw_models_path) as f:
                    data = json.load(f)
                providers = data.get("providers", {})
                for provider_name in [request.provider, "kimi-coding", "kimi"]:
                    if provider_name in providers:
                        provider_cfg = providers[provider_name]
                        openclaw_api_key = provider_cfg.get("apiKey")
                        openclaw_base_url = provider_cfg.get("baseUrl")
                        break
            except Exception:
                pass
        
        if request.provider == "ollama":
            kwargs["api_base"] = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        elif request.provider == "kimi" or request.provider == "kimi-coding":
            # Support kimi-coding API (anthropic-compatible)
            kwargs["api_base"] = openclaw_base_url or os.environ.get("KIMI_API_BASE", "https://api.kimi.com/coding")
            api_key = openclaw_api_key or os.environ.get("KIMI_API_KEY")
            if api_key:
                kwargs["api_key"] = api_key
            # Use anthropic as the actual provider for litellm
            request.provider = "anthropic"
            if "/" not in request.model:
                request.model = f"anthropic/{request.model}"
        elif request.provider == "moonshot":
            kwargs["api_base"] = os.environ.get("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")
            if os.environ.get("MOONSHOT_API_KEY"):
                kwargs["api_key"] = os.environ["MOONSHOT_API_KEY"]

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
        import sys
        import json

        kwargs = {}
        
        # Try to read OpenClaw config for API keys
        openclaw_models_path = os.path.expanduser("~/.openclaw/agents/main/agent/models.json")
        openclaw_api_key = None
        openclaw_base_url = None
        if os.path.exists(openclaw_models_path):
            try:
                with open(openclaw_models_path) as f:
                    data = json.load(f)
                providers = data.get("providers", {})
                for provider_name in [request.provider, "kimi-coding", "kimi"]:
                    if provider_name in providers:
                        provider_cfg = providers[provider_name]
                        openclaw_api_key = provider_cfg.get("apiKey")
                        openclaw_base_url = provider_cfg.get("baseUrl")
                        break
            except Exception:
                pass
        
        if request.provider == "ollama":
            kwargs["api_base"] = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        elif request.provider == "kimi" or request.provider == "kimi-coding":
            # Support kimi-coding API (anthropic-compatible)
            kwargs["api_base"] = openclaw_base_url or os.environ.get("KIMI_API_BASE", "https://api.kimi.com/coding")
            api_key = openclaw_api_key or os.environ.get("KIMI_API_KEY")
            if api_key:
                kwargs["api_key"] = api_key
            # Use anthropic as the actual provider for litellm
            request.provider = "anthropic"
            if "/" not in request.model:
                request.model = f"anthropic/{request.model}"
        elif request.provider == "moonshot":
            kwargs["api_base"] = os.environ.get("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")
            if os.environ.get("MOONSHOT_API_KEY"):
                kwargs["api_key"] = os.environ["MOONSHOT_API_KEY"]

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
        import json

        kwargs = {}
        
        # Try to read OpenClaw config for API keys
        openclaw_models_path = os.path.expanduser("~/.openclaw/agents/main/agent/models.json")
        openclaw_api_key = None
        openclaw_base_url = None
        if os.path.exists(openclaw_models_path):
            try:
                with open(openclaw_models_path) as f:
                    data = json.load(f)
                providers = data.get("providers", {})
                for provider_name in [request.provider, "kimi-coding", "kimi"]:
                    if provider_name in providers:
                        provider_cfg = providers[provider_name]
                        openclaw_api_key = provider_cfg.get("apiKey")
                        openclaw_base_url = provider_cfg.get("baseUrl")
                        break
            except Exception:
                pass
        
        if request.provider == "ollama":
            kwargs["api_base"] = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        elif request.provider == "kimi" or request.provider == "kimi-coding":
            # Support kimi-coding API (anthropic-compatible)
            kwargs["api_base"] = openclaw_base_url or os.environ.get("KIMI_API_BASE", "https://api.kimi.com/coding")
            api_key = openclaw_api_key or os.environ.get("KIMI_API_KEY")
            if api_key:
                kwargs["api_key"] = api_key
            # Use anthropic as the actual provider for litellm
            request.provider = "anthropic"
            if "/" not in request.model:
                request.model = f"anthropic/{request.model}"
        elif request.provider == "moonshot":
            kwargs["api_base"] = os.environ.get("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")
            if os.environ.get("MOONSHOT_API_KEY"):
                kwargs["api_key"] = os.environ["MOONSHOT_API_KEY"]

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
