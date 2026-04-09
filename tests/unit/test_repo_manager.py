from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deepwiki.data import repo_manager


def test_repo_type_detection() -> None:
    assert repo_manager._detect_repo_type("https://github.com/a/b", None) == "github"
    assert repo_manager._detect_repo_type("https://gitlab.com/a/b", None) == "gitlab"
    assert repo_manager._detect_repo_type("https://bitbucket.org/a/b", None) == "bitbucket"
    assert repo_manager._detect_repo_type("https://example.com/a/b", None) == "generic"
    assert repo_manager._detect_repo_type("https://example.com/a/b", "GitHub") == "github"


def test_auth_header_uses_provider_username() -> None:
    assert "eC1hY2Nlc3MtdG9rZW46dG9r" in repo_manager._build_auth_header("tok", "github")
    assert "b2F1dGgyOnRvaw==" in repo_manager._build_auth_header("tok", "gitlab")
    assert "eC10b2tlbi1hdXRoOnRvaw==" in repo_manager._build_auth_header("tok", "bitbucket")


def test_resolve_local_repo_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert repo_manager.resolve_repo_path(str(repo)) == repo.resolve()


def test_resolve_remote_uses_existing_cached_clone(monkeypatch, tmp_path: Path) -> None:
    remote = "https://github.com/acme/demo.git"
    clone_dir = tmp_path / "demo-cache"
    (clone_dir / ".git").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(repo_manager, "_target_clone_dir", lambda _: clone_dir)

    called = {"value": False}

    def fail_clone(**kwargs):
        called["value"] = True
        return clone_dir

    monkeypatch.setattr(repo_manager, "_git_clone", fail_clone)
    resolved = repo_manager.resolve_repo_path(remote)

    assert resolved == clone_dir.resolve()
    assert called["value"] is False


def test_git_clone_errors(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "repo"
    monkeypatch.setattr(repo_manager.shutil, "which", lambda _: "git")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git clone", timeout=120)

    monkeypatch.setattr(repo_manager.subprocess, "run", raise_timeout)
    with pytest.raises(ValueError, match="timeout"):
        repo_manager._git_clone("https://github.com/a/b.git", target, None, None)

    def raise_called_process(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd="git clone", stderr="auth failed")

    monkeypatch.setattr(repo_manager.subprocess, "run", raise_called_process)
    with pytest.raises(ValueError, match="auth failed"):
        repo_manager._git_clone("https://github.com/a/b.git", target, "fake", "github")
