from __future__ import annotations

import json
from pathlib import Path

from deepwiki.data.cache_manager import CacheManager


def test_cache_key_and_fingerprint_stability(tmp_path: Path) -> None:
    manager = CacheManager(str(tmp_path / ".cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    files = [("a.py", "print(1)"), ("b.py", "print(2)")]

    fp1 = manager.compute_repo_fingerprint(repo, files)
    fp2 = manager.compute_repo_fingerprint(repo, list(reversed(files)))
    assert fp1 == fp2

    key1 = manager.build_cache_key(repo, files, "openai", "e", 200, 20)
    key2 = manager.build_cache_key(repo, files, "openai", "e", 200, 20)
    assert key1 == key2
    assert len(key1) == 16


def test_cache_metadata_save_load_and_hit(tmp_path: Path) -> None:
    manager = CacheManager(str(tmp_path / ".cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    files = [("a.py", "print(1)")]
    key = manager.build_cache_key(repo, files, "openai", "e", 100, 10)

    metadata = manager.save_metadata(
        cache_key=key,
        repo_path=repo,
        files=files,
        embed_provider="openai",
        embed_model="e",
        chunk_size=100,
        chunk_overlap=10,
        chunk_count=3,
    )
    loaded = manager.load_metadata(key)
    assert loaded is not None
    assert loaded.cache_key == key
    assert loaded.chunk_count == 3
    assert metadata.repo_path == loaded.repo_path
    assert manager.is_cache_hit(key, repo, files, "openai", "e", 100, 10) is True


def test_cache_metadata_invalid_payload_and_mismatch(tmp_path: Path) -> None:
    manager = CacheManager(str(tmp_path / ".cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    files = [("a.py", "print(1)")]
    key = manager.build_cache_key(repo, files, "openai", "e", 100, 10)
    metadata_path = manager.metadata_path(key)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_path.write_text("{invalid", encoding="utf-8")
    assert manager.load_metadata(key) is None

    metadata_path.write_text(json.dumps({"cache_key": key}), encoding="utf-8")
    assert manager.load_metadata(key) is None

    manager.save_metadata(
        cache_key=key,
        repo_path=repo,
        files=files,
        embed_provider="openai",
        embed_model="e",
        chunk_size=100,
        chunk_overlap=10,
        chunk_count=1,
    )
    assert manager.is_cache_hit(key, repo, files, "other", "e", 100, 10) is False
    assert manager.is_cache_hit(key, repo, files, "openai", "other", 100, 10) is False
    assert manager.is_cache_hit(key, repo, files, "openai", "e", 101, 10) is False
    assert manager.is_cache_hit(key, repo, files, "openai", "e", 100, 11) is False
    assert manager.is_cache_hit(key, repo, [("b.py", "x")], "openai", "e", 100, 10) is False
