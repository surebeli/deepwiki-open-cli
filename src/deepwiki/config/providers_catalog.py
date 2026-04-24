from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_DEFAULT_CHAT_PROVIDERS: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "o4-mini"],
    "anthropic": ["claude-3-5-sonnet", "claude-3-7-sonnet", "claude-3-opus"],
    "google": ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash"],
    "ollama": ["ollama/qwen3:8b", "ollama/qwen3.5:9b", "ollama/llama3.1:8b"],
    "openrouter": ["openrouter/anthropic/claude-3.5-sonnet", "openrouter/openai/gpt-4o-mini"],
    "azure": ["azure/gpt-4o-mini", "azure/gpt-4o"],
    "bedrock": ["bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"],
    "kimi-coding": ["k2p5", "k2p6", "kimi-code"],
}

_DEFAULT_EMBED_PROVIDERS: dict[str, list[str]] = {
    "openai": ["text-embedding-3-small", "text-embedding-3-large"],
    "ollama": ["nomic-embed-text", "bge-m3"],
    "google": ["text-embedding-004", "gemini-embedding-001"],
    "voyage": ["voyage-3-lite", "voyage-large-2-instruct"],
}


def _catalog_file_path(file_name: str) -> Path:
    return Path(__file__).resolve().parent / file_name


def _dedupe_models(models: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for model in models:
        if model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


def _normalize_catalog(payload: Any) -> dict[str, list[str]]:
    catalog: dict[str, list[str]] = {}
    providers = payload.get("providers") if isinstance(payload, dict) else None
    if not isinstance(providers, list):
        return catalog

    for item in providers:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        models = item.get("models")
        if not isinstance(name, str) or not isinstance(models, list):
            continue
        model_names = [str(model) for model in models if isinstance(model, str) and model.strip()]
        if not model_names:
            continue
        catalog[name] = _dedupe_models(model_names)
    return catalog


def _read_catalog(file_name: str) -> dict[str, list[str]]:
    path = _catalog_file_path(file_name)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return _normalize_catalog(payload)


def _clone_catalog(catalog: dict[str, list[str]]) -> dict[str, list[str]]:
    return {name: list(models) for name, models in catalog.items()}


def load_provider_catalogs() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    chat_catalog = _read_catalog("generator.json")
    embed_catalog = _read_catalog("embedder.json")
    if not chat_catalog:
        chat_catalog = _clone_catalog(_DEFAULT_CHAT_PROVIDERS)
    if not embed_catalog:
        embed_catalog = _clone_catalog(_DEFAULT_EMBED_PROVIDERS)
    return chat_catalog, embed_catalog
