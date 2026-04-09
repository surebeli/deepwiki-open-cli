from __future__ import annotations

import json
from pathlib import Path

from deepwiki.cli.export import _markdown_readme, _offline_wiki, _slugify, _write_json_export, _write_markdown_export
from deepwiki.core.models import WikiPage, WikiResult


def test_slugify_and_markdown_readme() -> None:
    result = WikiResult(
        title="Demo Wiki",
        pages=[WikiPage(title="Intro & Setup", content="x"), WikiPage(title="API_Ref", content="y")],
    )
    readme = _markdown_readme(result)
    assert _slugify("Intro & Setup") == "intro-setup"
    assert "- [Intro & Setup](01-intro-setup.md)" in readme
    assert "- [API_Ref](02-api-ref.md)" in readme


def test_export_writers(tmp_path: Path) -> None:
    result = WikiResult(title="Demo", pages=[WikiPage(title="P1", content="body")])
    metadata = {"repo": "x"}

    md_dir = tmp_path / "md"
    _write_markdown_export(md_dir, result, metadata)
    assert (md_dir / "README.md").exists()
    assert (md_dir / "01-p1.md").exists()
    assert (md_dir / "diagrams").is_dir()
    assert json.loads((md_dir / "metadata.json").read_text(encoding="utf-8"))["repo"] == "x"

    json_dir = tmp_path / "json"
    _write_json_export(json_dir, result, metadata)
    payload = json.loads((json_dir / "wiki.json").read_text(encoding="utf-8"))
    assert payload["type"] == "wiki"
    assert payload["data"]["title"] == "Demo"


def test_offline_wiki_has_repo_title(tmp_path: Path) -> None:
    repo = tmp_path / "my-repo"
    repo.mkdir()
    result = _offline_wiki(repo, [("a.py", "print(1)")])
    assert result.title == "Wiki for my-repo"
