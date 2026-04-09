from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from deepwiki.cli.app import app


def test_generate_offline_smoke(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# demo", encoding="utf-8")
    (repo / "main.py").write_text("print('hello')", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["generate", str(repo), "--offline"])

    assert result.exit_code == 0
    assert "Wiki for repo" in result.output
