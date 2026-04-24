from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from deepwiki.cli import config_cmd
from deepwiki.config.settings import ResolvedSettings, SettingValue, Settings


def _resolved(top_k: int = 7) -> ResolvedSettings:
    settings = Settings(
        provider="openai",
        model="gpt-4o-mini",
        embed_provider="openai",
        embed_model="text-embedding-3-small",
        top_k=top_k,
        chunk_size=400,
        chunk_overlap=80,
        cache_dir=".cache/deepwiki",
    )
    return ResolvedSettings(
        settings=settings,
        sources={
            "provider": SettingValue("openai", "default", "defaults"),
            "model": SettingValue("gpt-4o-mini", "default", "defaults"),
            "embed_provider": SettingValue("openai", "default", "defaults"),
            "embed_model": SettingValue("text-embedding-3-small", "default", "defaults"),
            "top_k": SettingValue(top_k, "project", "project.yaml"),
            "chunk_size": SettingValue(400, "default", "defaults"),
            "chunk_overlap": SettingValue(80, "default", "defaults"),
            "cache_dir": SettingValue(".cache/deepwiki", "default", "defaults"),
        },
    )


def _app() -> typer.Typer:
    app = typer.Typer()
    config_cmd.register_config(app)
    return app


def test_config_path_and_set_json(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    user_cfg = tmp_path / "user-config.yaml"
    project_cfg = repo / ".deepwiki" / "config.yaml"

    monkeypatch.setattr(config_cmd, "user_config_path", lambda: user_cfg)
    monkeypatch.setattr(config_cmd, "project_config_path", lambda project_root: project_cfg)
    monkeypatch.setattr(config_cmd, "build_resolved_settings", lambda **kwargs: _resolved(top_k=12))

    runner = CliRunner()
    app = _app()

    result_path = runner.invoke(app, ["config", "path", str(repo), "--json"])
    assert result_path.exit_code == 0
    payload = json.loads(result_path.stdout.strip())
    assert payload["type"] == "config_path"
    # Cross-platform path check
    assert payload["data"]["project"].replace("\\", "/").endswith(".deepwiki/config.yaml")

    result_set = runner.invoke(app, ["config", "set", "top_k", "12", str(repo), "--scope", "project", "--json"])
    assert result_set.exit_code == 0
    set_payload = json.loads(result_set.stdout.strip())
    assert set_payload["type"] == "config_set"
    assert set_payload["data"]["written_value"] == 12
    assert json.loads(json.dumps({"x": 1}))["x"] == 1


def test_config_init_and_providers_json(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    project_cfg = repo / ".deepwiki" / "config.yaml"
    user_cfg = tmp_path / "user-config.yaml"

    monkeypatch.setattr(config_cmd, "user_config_path", lambda: user_cfg)
    monkeypatch.setattr(config_cmd, "project_config_path", lambda project_root: project_cfg)
    monkeypatch.setattr(config_cmd, "build_resolved_settings", lambda **kwargs: _resolved(top_k=5))
    monkeypatch.setattr(
        config_cmd,
        "load_provider_catalogs",
        lambda: ({"openai": ["gpt-4o-mini"]}, {"openai": ["text-embedding-3-small"]}),
    )

    runner = CliRunner()
    app = _app()

    init_input = "\n".join(
        [
            "openai",
            "gpt-4o-mini",
            "openai",
            "text-embedding-3-small",
            "5",
            "400",
            "80",
            ".cache/deepwiki",
        ]
    ) + "\n"
    result_init = runner.invoke(app, ["config", "init", str(repo), "--scope", "project", "--json"], input=init_input)
    assert result_init.exit_code == 0
    init_payload = json.loads(result_init.stdout.strip().splitlines()[-1])
    assert init_payload["type"] == "config_init"
    assert project_cfg.exists()

    result_providers = runner.invoke(app, ["config", "providers", str(repo), "--json"])
    assert result_providers.exit_code == 0
    providers_payload = json.loads(result_providers.stdout.strip())
    assert providers_payload["type"] == "providers"


def test_config_helpers_and_plain_text_paths(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    project_cfg = repo / ".deepwiki" / "config.yaml"
    user_cfg = tmp_path / "user-config.yaml"

    monkeypatch.setattr(config_cmd, "user_config_path", lambda: user_cfg)
    monkeypatch.setattr(config_cmd, "project_config_path", lambda project_root: project_cfg)
    monkeypatch.setattr(config_cmd, "build_resolved_settings", lambda **kwargs: _resolved(top_k=9))
    monkeypatch.setattr(
        config_cmd,
        "load_provider_catalogs",
        lambda: ({"openai": ["gpt-4o-mini", "gpt-4.1"]}, {"openai": ["text-embedding-3-small"]}),
    )

    app = _app()
    runner = CliRunner()

    result_show = runner.invoke(app, ["config", "show", str(repo)])
    assert result_show.exit_code == 0
    assert "Project Root:" in result_show.stdout
    assert "top_k: 9" in result_show.stdout

    result_providers = runner.invoke(app, ["config", "providers", str(repo)])
    assert result_providers.exit_code == 0
    assert "Generation Providers:" in result_providers.stdout
    assert "* indicates effective settings" in result_providers.stdout

    result_path = runner.invoke(app, ["config", "path", str(repo)])
    assert result_path.exit_code == 0
    assert "user:" in result_path.stdout
    assert "project_root:" in result_path.stdout


def test_config_set_and_validation_errors(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    project_cfg = repo / ".deepwiki" / "config.yaml"
    user_cfg = tmp_path / "user-config.yaml"

    monkeypatch.setattr(config_cmd, "user_config_path", lambda: user_cfg)
    monkeypatch.setattr(config_cmd, "project_config_path", lambda project_root: project_cfg)
    monkeypatch.setattr(config_cmd, "build_resolved_settings", lambda **kwargs: _resolved(top_k=13))

    app = _app()
    runner = CliRunner()

    result_set = runner.invoke(app, ["config", "set", "top-k", "13", str(repo), "--scope", "project"])
    assert result_set.exit_code == 0
    assert "Updated top_k in" in result_set.stdout
    assert "effective: 13" in result_set.stdout

    result_bad_scope = runner.invoke(app, ["config", "set", "top_k", "3", str(repo), "--scope", "bad"])
    assert result_bad_scope.exit_code != 0
    assert "scope must be one of: user, project" in result_bad_scope.stdout

    result_bad_key = runner.invoke(app, ["config", "set", "not_exist", "3", str(repo)])
    assert result_bad_key.exit_code != 0
    assert "Unsupported key" in result_bad_key.stdout

    result_bad_int = runner.invoke(app, ["config", "set", "top_k", "abc", str(repo)])
    assert result_bad_int.exit_code != 0
    assert "top_k expects an integer value" in result_bad_int.stdout


def test_config_misc_helpers() -> None:
    assert config_cmd._normalize_key(" TOP-K ") == "top_k"
    assert config_cmd._coerce_value("provider", "openai") == "openai"
    assert config_cmd._coerce_value("top_k", "7") == 7


def test_resolve_project_root_and_read_config_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert config_cmd._resolve_project_root(str(repo)) == repo.resolve()

    missing = tmp_path / "missing.yaml"
    assert config_cmd._read_config_file(missing) == {}

    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text(":\n::", encoding="utf-8")
    assert config_cmd._read_config_file(invalid_yaml) == {}
