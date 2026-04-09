from pathlib import Path

from deepwiki.agent.detector import AgentContext, AgentDetector
from deepwiki.config.settings import ResolvedSettings, Settings, load_settings, resolve_settings
from deepwiki.providers.litellm_provider import LiteLLMProvider


def _detect_agent_context(provider: str | None) -> AgentContext | None:
    if provider is not None:
        return None
    return AgentDetector.detect()


def build_resolved_settings(
    provider: str | None = None,
    model: str | None = None,
    embed_provider: str | None = None,
    embed_model: str | None = None,
    top_k: int | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    cache_dir: str | None = None,
    project_root: Path | None = None,
) -> ResolvedSettings:
    agent_context = _detect_agent_context(provider)
    return resolve_settings(
        provider_override=provider,
        model_override=model,
        embed_provider_override=embed_provider,
        embed_model_override=embed_model,
        top_k_override=top_k,
        chunk_size_override=chunk_size,
        chunk_overlap_override=chunk_overlap,
        cache_dir_override=cache_dir,
        project_root=project_root,
        agent_context=agent_context,
    )


def build_runtime(
    provider: str | None = None,
    model: str | None = None,
    embed_provider: str | None = None,
    embed_model: str | None = None,
    top_k: int | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    cache_dir: str | None = None,
    project_root: Path | None = None,
) -> tuple[Settings, LiteLLMProvider]:
    agent_context = _detect_agent_context(provider)
    settings = load_settings(
        provider_override=provider,
        model_override=model,
        embed_provider_override=embed_provider,
        embed_model_override=embed_model,
        top_k_override=top_k,
        chunk_size_override=chunk_size,
        chunk_overlap_override=chunk_overlap,
        cache_dir_override=cache_dir,
        project_root=project_root,
        agent_context=agent_context,
    )
    runtime_provider = LiteLLMProvider()
    return settings, runtime_provider
