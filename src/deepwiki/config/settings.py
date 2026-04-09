from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepwiki.agent.detector import AgentContext
from deepwiki.config.defaults import get_defaults

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class Settings:
    provider: str
    model: str
    embed_provider: str
    embed_model: str
    top_k: int
    chunk_size: int
    chunk_overlap: int
    cache_dir: str


@dataclass
class SettingValue:
    value: str | int
    source: str
    origin: str


@dataclass
class ResolvedSettings:
    settings: Settings
    sources: dict[str, SettingValue]


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None or not path.exists() or not path.is_file():
        return {}

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return payload if isinstance(payload, dict) else {}


def _user_config_path() -> Path:
    return Path.home() / ".deepwiki" / "config.yaml"


def _project_config_path(project_root: Path | None) -> Path:
    root = project_root.resolve() if project_root is not None else Path.cwd().resolve()
    return root / ".deepwiki" / "config.yaml"


def user_config_path() -> Path:
    return _user_config_path()


def project_config_path(project_root: Path | None) -> Path:
    return _project_config_path(project_root)


def _normalize_config_values(payload: dict[str, Any]) -> dict[str, str | int]:
    provider_cfg = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
    embedder_cfg = payload.get("embedder") if isinstance(payload.get("embedder"), dict) else {}
    rag_cfg = payload.get("rag") if isinstance(payload.get("rag"), dict) else {}

    values: dict[str, str | int] = {}

    provider_value = payload.get("provider")
    if isinstance(provider_value, str):
        values["provider"] = provider_value
    provider_name = provider_cfg.get("name")
    if isinstance(provider_name, str):
        values["provider"] = provider_name

    model_value = payload.get("model")
    if isinstance(model_value, str):
        values["model"] = model_value
    provider_model = provider_cfg.get("model")
    if isinstance(provider_model, str):
        values["model"] = provider_model

    embed_provider_value = payload.get("embed_provider")
    if isinstance(embed_provider_value, str):
        values["embed_provider"] = embed_provider_value
    embedder_provider = embedder_cfg.get("provider")
    if isinstance(embedder_provider, str):
        values["embed_provider"] = embedder_provider

    embed_model_value = payload.get("embed_model")
    if isinstance(embed_model_value, str):
        values["embed_model"] = embed_model_value
    embedder_model = embedder_cfg.get("model")
    if isinstance(embedder_model, str):
        values["embed_model"] = embedder_model

    cache_dir = payload.get("cache_dir")
    if isinstance(cache_dir, str):
        values["cache_dir"] = cache_dir

    top_k = rag_cfg.get("top_k", payload.get("top_k"))
    chunk_size = rag_cfg.get("chunk_size", payload.get("chunk_size"))
    chunk_overlap = rag_cfg.get("chunk_overlap", payload.get("chunk_overlap"))

    parsed_top_k = _coerce_int(top_k)
    if parsed_top_k is not None:
        values["top_k"] = parsed_top_k

    parsed_chunk_size = _coerce_int(chunk_size)
    if parsed_chunk_size is not None:
        values["chunk_size"] = parsed_chunk_size

    parsed_chunk_overlap = _coerce_int(chunk_overlap)
    if parsed_chunk_overlap is not None:
        values["chunk_overlap"] = parsed_chunk_overlap

    return values


def _env_values() -> tuple[dict[str, str | int], dict[str, str]]:
    mapping = {
        "provider": "DEEPWIKI_PROVIDER",
        "model": "DEEPWIKI_MODEL",
        "embed_provider": "DEEPWIKI_EMBED_PROVIDER",
        "embed_model": "DEEPWIKI_EMBED_MODEL",
        "cache_dir": "DEEPWIKI_CACHE_DIR",
    }

    values: dict[str, str | int] = {}
    origins: dict[str, str] = {}

    for field, env_name in mapping.items():
        value = os.getenv(env_name)
        if value is None or value == "":
            continue
        values[field] = value
        origins[field] = env_name

    int_mapping = {
        "top_k": "DEEPWIKI_TOP_K",
        "chunk_size": "DEEPWIKI_CHUNK_SIZE",
        "chunk_overlap": "DEEPWIKI_CHUNK_OVERLAP",
    }
    for field, env_name in int_mapping.items():
        value = os.getenv(env_name)
        if value is None or value == "":
            continue
        parsed = _coerce_int(value)
        if parsed is None:
            continue
        values[field] = parsed
        origins[field] = env_name

    return values, origins


def _apply_layer(
    values: dict[str, str | int],
    sources: dict[str, SettingValue],
    layer_values: dict[str, str | int],
    source: str,
    origins: dict[str, str] | None = None,
) -> None:
    for field, value in layer_values.items():
        values[field] = value
        origin = origins[field] if origins and field in origins else source
        sources[field] = SettingValue(value=value, source=source, origin=origin)


def resolve_settings(
    provider_override: str | None = None,
    model_override: str | None = None,
    embed_provider_override: str | None = None,
    embed_model_override: str | None = None,
    top_k_override: int | None = None,
    chunk_size_override: int | None = None,
    chunk_overlap_override: int | None = None,
    cache_dir_override: str | None = None,
    project_root: Path | None = None,
    agent_context: AgentContext | None = None,
) -> ResolvedSettings:
    defaults = get_defaults()

    values: dict[str, str | int] = {
        "provider": defaults.provider,
        "model": defaults.model,
        "embed_provider": defaults.embed_provider,
        "embed_model": defaults.embed_model,
        "top_k": defaults.top_k,
        "chunk_size": defaults.chunk_size,
        "chunk_overlap": defaults.chunk_overlap,
        "cache_dir": defaults.cache_dir,
    }

    sources: dict[str, SettingValue] = {
        key: SettingValue(value=value, source="default", origin="defaults")
        for key, value in values.items()
    }

    user_config_path = _user_config_path()
    user_values = _normalize_config_values(_read_yaml(user_config_path))
    _apply_layer(
        values=values,
        sources=sources,
        layer_values=user_values,
        source="user",
        origins={key: str(user_config_path) for key in user_values},
    )

    project_config_path = _project_config_path(project_root)
    project_values = _normalize_config_values(_read_yaml(project_config_path))
    _apply_layer(
        values=values,
        sources=sources,
        layer_values=project_values,
        source="project",
        origins={key: str(project_config_path) for key in project_values},
    )

    env_values, env_origins = _env_values()
    _apply_layer(
        values=values,
        sources=sources,
        layer_values=env_values,
        source="env",
        origins=env_origins,
    )

    agent_values: dict[str, str | int] = {}
    agent_origins: dict[str, str] = {}
    if agent_context is not None and agent_context.passthrough_available:
        if agent_context.provider is not None:
            agent_values["provider"] = agent_context.provider
            agent_origins["provider"] = agent_context.agent_name
        if agent_context.model is not None:
            agent_values["model"] = agent_context.model
            agent_origins["model"] = agent_context.agent_name

    _apply_layer(
        values=values,
        sources=sources,
        layer_values=agent_values,
        source="agent",
        origins=agent_origins,
    )

    cli_values: dict[str, str | int] = {}
    cli_origins: dict[str, str] = {}
    if provider_override is not None:
        cli_values["provider"] = provider_override
        cli_origins["provider"] = "--provider"
    if model_override is not None:
        cli_values["model"] = model_override
        cli_origins["model"] = "--model"
    if embed_provider_override is not None:
        cli_values["embed_provider"] = embed_provider_override
        cli_origins["embed_provider"] = "--embed-provider"
    if embed_model_override is not None:
        cli_values["embed_model"] = embed_model_override
        cli_origins["embed_model"] = "--embed-model"
    if top_k_override is not None:
        cli_values["top_k"] = top_k_override
        cli_origins["top_k"] = "--top-k"
    if chunk_size_override is not None:
        cli_values["chunk_size"] = chunk_size_override
        cli_origins["chunk_size"] = "--chunk-size"
    if chunk_overlap_override is not None:
        cli_values["chunk_overlap"] = chunk_overlap_override
        cli_origins["chunk_overlap"] = "--chunk-overlap"
    if cache_dir_override is not None:
        cli_values["cache_dir"] = cache_dir_override
        cli_origins["cache_dir"] = "--cache-dir"

    _apply_layer(
        values=values,
        sources=sources,
        layer_values=cli_values,
        source="cli",
        origins=cli_origins,
    )

    settings = Settings(
        provider=str(values["provider"]),
        model=str(values["model"]),
        embed_provider=str(values["embed_provider"]),
        embed_model=str(values["embed_model"]),
        top_k=int(values["top_k"]),
        chunk_size=int(values["chunk_size"]),
        chunk_overlap=int(values["chunk_overlap"]),
        cache_dir=str(values["cache_dir"]),
    )
    return ResolvedSettings(settings=settings, sources=sources)


def load_settings(
    provider_override: str | None = None,
    model_override: str | None = None,
    embed_provider_override: str | None = None,
    embed_model_override: str | None = None,
    top_k_override: int | None = None,
    chunk_size_override: int | None = None,
    chunk_overlap_override: int | None = None,
    cache_dir_override: str | None = None,
    project_root: Path | None = None,
    agent_context: AgentContext | None = None,
) -> Settings:
    return resolve_settings(
        provider_override=provider_override,
        model_override=model_override,
        embed_provider_override=embed_provider_override,
        embed_model_override=embed_model_override,
        top_k_override=top_k_override,
        chunk_size_override=chunk_size_override,
        chunk_overlap_override=chunk_overlap_override,
        cache_dir_override=cache_dir_override,
        project_root=project_root,
        agent_context=agent_context,
    ).settings
