from __future__ import annotations

import json
from pathlib import Path

from deepwiki.config import providers_catalog


def test_normalize_catalog_and_dedupe() -> None:
    payload = {
        "providers": [
            {"name": "openai", "models": ["gpt-4o-mini", "gpt-4o-mini", "gpt-4o"]},
            {"name": "bad", "models": []},
            {"name": 1, "models": ["x"]},
        ]
    }
    normalized = providers_catalog._normalize_catalog(payload)
    assert normalized["openai"] == ["gpt-4o-mini", "gpt-4o"]
    assert "bad" not in normalized


def test_load_provider_catalogs_from_files(monkeypatch, tmp_path: Path) -> None:
    generator = tmp_path / "generator.json"
    embedder = tmp_path / "embedder.json"
    generator.write_text(json.dumps({"providers": [{"name": "x", "models": ["m1"]}]}), encoding="utf-8")
    embedder.write_text(json.dumps({"providers": [{"name": "y", "models": ["e1"]}]}), encoding="utf-8")

    monkeypatch.setattr(providers_catalog, "_catalog_file_path", lambda name: tmp_path / name)
    chat, embed = providers_catalog.load_provider_catalogs()

    assert chat == {"x": ["m1"]}
    assert embed == {"y": ["e1"]}


def test_load_provider_catalogs_fallback_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(providers_catalog, "_catalog_file_path", lambda name: tmp_path / name)
    chat, embed = providers_catalog.load_provider_catalogs()

    assert "openai" in chat
    assert "openai" in embed
