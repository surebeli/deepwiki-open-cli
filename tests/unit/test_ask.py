from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from deepwiki.cli import ask
from deepwiki.config.settings import Settings
from deepwiki.core.models import AnswerSource, AskResult


def _app() -> typer.Typer:
    app = typer.Typer()
    ask.register_ask(app)
    return app


def test_run_ask_turn() -> None:
    class _Engine:
        async def answer(self, **kwargs):
            return AskResult(answer="ok", sources=[], metadata={"m": 1})

    result = ask.run_ask_turn(
        engine=_Engine(),
        repo_path=Path("."),
        files=[("a.py", "x")],
        question="q",
        settings=Settings("openai", "m", "openai", "e", 3, 100, 10, ".cache"),
        top_k=2,
        use_cache=True,
    )
    assert result.answer == "ok"


def test_ask_command_json_and_plain(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(ask, "resolve_repo_path", lambda *args, **kwargs: repo)
    monkeypatch.setattr(ask, "read_repo_files", lambda *args, **kwargs: [("a.py", "x")])
    monkeypatch.setattr(
        ask,
        "build_runtime",
        lambda **kwargs: (
            Settings("openai", "m", "openai", "e", 3, 100, 10, str(tmp_path / ".cache")),
            object(),
        ),
    )

    class _Engine:
        def __init__(self, provider) -> None:
            pass

        async def answer(self, **kwargs):
            return AskResult(
                answer="answer-text",
                sources=[AnswerSource(file_path="a.py", chunk_preview="x", relevance_score=0.9)],
                metadata={"index_cached": False},
            )

    monkeypatch.setattr(ask, "RAGEngine", _Engine)

    runner = CliRunner()
    app = _app()
    result_json = runner.invoke(app, [str(repo), "question", "--json"])
    assert result_json.exit_code == 0
    payload = json.loads(result_json.stdout.strip())
    assert payload["type"] == "answer"
    assert payload["data"]["answer"] == "answer-text"

    result_plain = runner.invoke(app, [str(repo), "question"])
    assert result_plain.exit_code == 0
    assert "answer-text" in result_plain.stdout
    assert "Sources:" in result_plain.stdout
