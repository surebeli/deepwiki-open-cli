from __future__ import annotations

import json
from pathlib import Path

from deepwiki.config.settings import ResolvedSettings, SettingValue, Settings
from deepwiki.output.json_output import JSONFormatter


def test_mask_value_for_secret_like_fields() -> None:
    formatter = JSONFormatter()

    assert formatter._mask_value("api_key", "abcdefgh12345678") == "abcd****5678"
    assert formatter._mask_value("token", "short") == "****"
    assert formatter._mask_value("provider", "openai") == "openai"


def test_render_config_redacts_project_root(capsys, tmp_path: Path) -> None:
    formatter = JSONFormatter()
    project_root = tmp_path / "repo"
    project_root.mkdir()
    resolved = ResolvedSettings(
        settings=Settings("openai", "m", "openai", "e", 3, 100, 10, ".cache"),
        sources={
            "provider": SettingValue("openai", "default", "defaults"),
            "model": SettingValue("m", "default", "defaults"),
            "embed_provider": SettingValue("openai", "default", "defaults"),
            "embed_model": SettingValue("e", "default", "defaults"),
            "top_k": SettingValue(3, "default", "defaults"),
            "chunk_size": SettingValue(100, "default", "defaults"),
            "chunk_overlap": SettingValue(10, "default", "defaults"),
            "cache_dir": SettingValue(".cache", "default", "defaults"),
        },
    )

    formatter.render_config(resolved, project_root)
    payload = json.loads(capsys.readouterr().out)
    assert payload["metadata"]["project_root"] == "repo"
