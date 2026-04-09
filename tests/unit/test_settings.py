from __future__ import annotations

from pathlib import Path

from deepwiki.config.settings import resolve_settings


def test_settings_precedence_cli_over_env_project_user(monkeypatch, tmp_path: Path) -> None:
    user_home = tmp_path / "home"
    project_root = tmp_path / "project"
    user_cfg = user_home / ".deepwiki" / "config.yaml"
    project_cfg = project_root / ".deepwiki" / "config.yaml"
    user_cfg.parent.mkdir(parents=True, exist_ok=True)
    project_cfg.parent.mkdir(parents=True, exist_ok=True)

    user_cfg.write_text("provider: user-provider\nmodel: user-model\n", encoding="utf-8")
    project_cfg.write_text("provider: project-provider\nmodel: project-model\n", encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: user_home)
    monkeypatch.setenv("DEEPWIKI_PROVIDER", "env-provider")

    resolved = resolve_settings(
        provider_override="cli-provider",
        model_override="cli-model",
        project_root=project_root,
    )

    assert resolved.settings.provider == "cli-provider"
    assert resolved.settings.model == "cli-model"
    assert resolved.sources["provider"].source == "cli"
    assert resolved.sources["provider"].origin == "--provider"


def test_settings_support_nested_rag_values(monkeypatch, tmp_path: Path) -> None:
    user_home = tmp_path / "home"
    project_root = tmp_path / "project"
    cfg = project_root / ".deepwiki" / "config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "provider:\n"
        "  name: ollama\n"
        "  model: ollama/qwen3.5:9b\n"
        "embedder:\n"
        "  provider: ollama\n"
        "  model: nomic-embed-text\n"
        "rag:\n"
        "  top_k: 11\n"
        "  chunk_size: 333\n"
        "  chunk_overlap: 77\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(Path, "home", lambda: user_home)
    resolved = resolve_settings(project_root=project_root)

    assert resolved.settings.provider == "ollama"
    assert resolved.settings.model == "ollama/qwen3.5:9b"
    assert resolved.settings.embed_provider == "ollama"
    assert resolved.settings.embed_model == "nomic-embed-text"
    assert resolved.settings.top_k == 11
    assert resolved.settings.chunk_size == 333
    assert resolved.settings.chunk_overlap == 77
