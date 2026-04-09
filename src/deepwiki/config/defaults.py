import os
from dataclasses import dataclass
from pathlib import Path


def _default_cache_dir() -> str:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return str(Path(local_app_data) / "deepwiki")
    return str(Path.home() / ".cache" / "deepwiki")


@dataclass
class ProviderDefaults:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    embed_provider: str = "ollama"
    embed_model: str = "nomic-embed-text"
    top_k: int = 20
    chunk_size: int = 350
    chunk_overlap: int = 100
    cache_dir: str = _default_cache_dir()


def get_defaults() -> ProviderDefaults:
    return ProviderDefaults()
