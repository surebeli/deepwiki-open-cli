from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


CACHE_SCHEMA_VERSION = "v2"


@dataclass
class IndexMetadata:
    cache_key: str
    repo_path: str
    repo_fingerprint: str
    file_count: int
    embed_provider: str
    embed_model: str
    chunk_size: int
    chunk_overlap: int
    chunk_count: int
    created_at: str


class CacheManager:
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.index_root = self.cache_dir / "indexes"
        self.index_root.mkdir(parents=True, exist_ok=True)

    def build_cache_key(
        self,
        repo_path: Path,
        files: list[tuple[str, str]],
        embed_provider: str,
        embed_model: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> str:
        repo_fingerprint = self.compute_repo_fingerprint(repo_path=repo_path, files=files)
        raw = ":".join(
            [
                CACHE_SCHEMA_VERSION,
                str(repo_path.resolve()),
                repo_fingerprint,
                embed_provider,
                embed_model,
                str(chunk_size),
                str(chunk_overlap),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def compute_repo_fingerprint(self, repo_path: Path, files: list[tuple[str, str]]) -> str:
        digest = hashlib.sha256()
        digest.update(str(repo_path.resolve()).encode("utf-8"))

        for file_path, content in sorted(files, key=lambda item: item[0]):
            digest.update(file_path.encode("utf-8"))
            content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            digest.update(content_hash.encode("utf-8"))

        return digest.hexdigest()[:16]

    def index_path(self, cache_key: str) -> Path:
        return self.index_root / cache_key

    def metadata_path(self, cache_key: str) -> Path:
        return self.index_path(cache_key) / "metadata.json"

    def load_metadata(self, cache_key: str) -> IndexMetadata | None:
        path = self.metadata_path(cache_key)
        if not path.exists() or not path.is_file():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

        try:
            return IndexMetadata(**payload)
        except TypeError:
            return None

    def is_cache_hit(
        self,
        cache_key: str,
        repo_path: Path,
        files: list[tuple[str, str]],
        embed_provider: str,
        embed_model: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> bool:
        metadata = self.load_metadata(cache_key)
        if metadata is None:
            return False

        expected_fingerprint = self.compute_repo_fingerprint(repo_path=repo_path, files=files)
        if metadata.repo_fingerprint != expected_fingerprint:
            return False
        if metadata.embed_provider != embed_provider:
            return False
        if metadata.embed_model != embed_model:
            return False
        if metadata.chunk_size != chunk_size:
            return False
        if metadata.chunk_overlap != chunk_overlap:
            return False
        if metadata.file_count != len(files):
            return False

        return self.index_path(cache_key).exists()

    def save_metadata(
        self,
        cache_key: str,
        repo_path: Path,
        files: list[tuple[str, str]],
        embed_provider: str,
        embed_model: str,
        chunk_size: int,
        chunk_overlap: int,
        chunk_count: int,
    ) -> IndexMetadata:
        repo_fingerprint = self.compute_repo_fingerprint(repo_path=repo_path, files=files)
        metadata = IndexMetadata(
            cache_key=cache_key,
            repo_path=str(repo_path.resolve()),
            repo_fingerprint=repo_fingerprint,
            file_count=len(files),
            embed_provider=embed_provider,
            embed_model=embed_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunk_count=chunk_count,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        target_dir = self.index_path(cache_key)
        target_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path(cache_key).write_text(
            json.dumps(asdict(metadata), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return metadata
