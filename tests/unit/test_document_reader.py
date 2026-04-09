from __future__ import annotations

from pathlib import Path

from deepwiki.data.document_reader import read_repo_files


def test_document_reader_filters_extensions_and_git_dir(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("print('ok')", encoding="utf-8")
    (repo / "notes.md").write_text("# title", encoding="utf-8")
    (repo / "binary.bin").write_bytes(b"\x00\x01")
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("ignored", encoding="utf-8")

    files = read_repo_files(repo, limit=20)
    paths = {p for p, _ in files}

    assert "a.py" in paths
    assert "notes.md" in paths
    assert "binary.bin" not in paths
    assert ".git/config" not in paths


def test_document_reader_respects_limit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for idx in range(5):
        (repo / f"f{idx}.py").write_text(f"print({idx})", encoding="utf-8")

    files = read_repo_files(repo, limit=3)
    assert len(files) == 3
