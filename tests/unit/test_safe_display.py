from __future__ import annotations

from pathlib import Path

from deepwiki.output.safe_display import display_config_path, display_project_root, display_repo_ref


def test_display_repo_and_project_root_only_use_basename(tmp_path: Path) -> None:
    repo = tmp_path / "nested" / "repo"
    repo.mkdir(parents=True)
    assert display_repo_ref(repo) == "repo"
    assert display_project_root(repo) == "repo"


def test_display_config_path_redacts_absolute_location(tmp_path: Path) -> None:
    project_cfg = tmp_path / "repo" / ".deepwiki" / "config.yaml"
    project_cfg.parent.mkdir(parents=True)
    project_cfg.write_text("", encoding="utf-8")
    user_cfg = tmp_path / "user-config.yaml"
    user_cfg.write_text("", encoding="utf-8")

    assert display_config_path(project_cfg).endswith(".deepwiki\\config.yaml")
    assert display_config_path(user_cfg) == "user-config.yaml"
