import os
import json
from dataclasses import dataclass
from pathlib import Path


def _default_cache_dir() -> str:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return str(Path(local_app_data) / "deepwiki")
    return str(Path.home() / ".cache" / "deepwiki")


def _get_openclaw_kimi_config() -> dict | None:
    """Read OpenClaw's kimi-coding configuration if available."""
    openclaw_models_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "models.json"
    if not openclaw_models_path.exists():
        return None
    
    try:
        data = json.loads(openclaw_models_path.read_text())
        providers = data.get("providers", {})
        
        # Try kimi-coding first, then kimi
        for provider_name in ["kimi-coding", "kimi"]:
            if provider_name in providers:
                provider = providers[provider_name]
                models = provider.get("models", [])
                if models:
                    return {
                        "provider": provider_name,
                        "model": models[0]["id"],
                        "api_key": provider.get("apiKey", ""),
                        "base_url": provider.get("baseUrl", "https://api.kimi.com/coding/"),
                        "api_type": provider.get("api", "anthropic-messages"),
                    }
    except Exception:
        pass
    
    return None


@dataclass
class ProviderDefaults:
    provider: str = "ollama"
    model: str = "qwen3:8b"
    embed_provider: str = "ollama"
    embed_model: str = "nomic-embed-text"
    top_k: int = 20
    chunk_size: int = 350
    chunk_overlap: int = 100
    cache_dir: str = _default_cache_dir()


def get_defaults() -> ProviderDefaults:
    """Get defaults from environment, OpenClaw config, or fallback to Ollama."""
    
    # Check if OpenClaw kimi config exists
    openclaw_config = _get_openclaw_kimi_config()
    
    if openclaw_config and openclaw_config.get("api_key"):
        # Use OpenClaw's kimi-coding configuration
        return ProviderDefaults(
            provider=openclaw_config["provider"],
            model=openclaw_config["model"],
            embed_provider="ollama",
            embed_model="nomic-embed-text",
        )
    
    # Check environment variables
    env_provider = os.getenv("DEEPWIKI_PROVIDER")
    env_model = os.getenv("DEEPWIKI_MODEL")
    
    if env_provider and env_model:
        return ProviderDefaults(
            provider=env_provider,
            model=env_model,
            embed_provider=os.getenv("DEEPWIKI_EMBED_PROVIDER", "ollama"),
            embed_model=os.getenv("DEEPWIKI_EMBED_MODEL", "nomic-embed-text"),
        )
    
    # Fallback to Ollama defaults
    return ProviderDefaults()
