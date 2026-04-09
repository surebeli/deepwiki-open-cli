from __future__ import annotations

from pathlib import Path

import typer
from typer.testing import CliRunner

from deepwiki.cli import repl
from deepwiki.config.settings import Settings
from deepwiki.core.models import AnswerSource, AskResult


def _app() -> typer.Typer:
    app = typer.Typer()
    repl.register_repl(app)
    return app


def test_repl_helper_output(capsys) -> None:
    repl._print_help()
    repl._render_answer("ok", [AnswerSource(file_path="a.py", chunk_preview="x", relevance_score=0.8)])
    out = capsys.readouterr().out
    assert "Commands:" in out
    assert "Sources:" in out


def test_repl_command_flow(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(repl, "resolve_repo_path", lambda *args, **kwargs: repo)
    monkeypatch.setattr(
        repl,
        "build_runtime",
        lambda **kwargs: (
            Settings("openai", "m", "openai", "e", 3, 100, 10, str(tmp_path / ".cache")),
            object(),
        ),
    )
    monkeypatch.setattr(repl, "read_repo_files", lambda *args, **kwargs: [("a.py", "x")])

    class _Engine:
        def __init__(self, provider) -> None:
            pass

    monkeypatch.setattr(repl, "RAGEngine", _Engine)
    monkeypatch.setattr(
        repl,
        "run_ask_turn",
        lambda **kwargs: AskResult(
            answer="repl-answer",
            sources=[AnswerSource(file_path="a.py", chunk_preview="x", relevance_score=0.7)],
            metadata={},
        ),
    )

    app = _app()
    runner = CliRunner()
    result = runner.invoke(app, [str(repo)], input="/help\n/clear\nquestion?\n/quit\n")
    assert result.exit_code == 0
    assert "DeepWiki REPL for repo" in result.stdout
    assert "Session history cleared." in result.stdout
    assert "repl-answer" in result.stdout


def test_repl_handles_ask_error(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(repl, "resolve_repo_path", lambda *args, **kwargs: repo)
    monkeypatch.setattr(
        repl,
        "build_runtime",
        lambda **kwargs: (
            Settings("openai", "m", "openai", "e", 3, 100, 10, str(tmp_path / ".cache")),
            object(),
        ),
    )
    monkeypatch.setattr(repl, "read_repo_files", lambda *args, **kwargs: [("a.py", "x")])
    monkeypatch.setattr(repl, "RAGEngine", lambda provider: object())

    def _raise(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(repl, "run_ask_turn", _raise)
    app = _app()
    runner = CliRunner()
    result = runner.invoke(app, [str(repo)], input="question?\n/quit\n")
    assert result.exit_code == 0
    assert "Error: boom" in result.stdout
