from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from deepwiki.cli import research
from deepwiki.config.settings import Settings
from deepwiki.core.models import AnswerSource, AskResult


def _app() -> typer.Typer:
    app = typer.Typer()
    research.register_research(app)
    return app


def test_research_helpers() -> None:
    q1 = research._build_iteration_question("topic", [], 0)
    assert "Research topic: topic" in q1
    q2 = research._build_iteration_question("topic", ["x" * 900], 1)
    assert "Continue researching topic: topic" in q2
    assert len(q2) < 1200

    follow_ups = research._extract_follow_ups("- What is next?\n- Why now?\n- no question")
    assert follow_ups == ["What is next?", "Why now?"]
    fallback = research._extract_follow_ups("plain statement")
    assert "What repository area should be inspected next" in fallback[0]


def test_research_dedupe_sources_keeps_higher_relevance() -> None:
    a = AnswerSource(file_path="a.py", chunk_preview="same", relevance_score=0.3)
    b = AnswerSource(file_path="a.py", chunk_preview="same", relevance_score=0.9)
    c = AnswerSource(file_path="b.py", chunk_preview="other", relevance_score=0.5)
    merged = research._dedupe_sources(
        [
            AskResult(answer="x", sources=[a, c], metadata={}),
            AskResult(answer="y", sources=[b], metadata={}),
        ]
    )
    assert len(merged) == 2
    assert merged[0].relevance_score == 0.9


def test_research_command_json_and_plain_output(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(research, "resolve_repo_path", lambda *args, **kwargs: repo)
    monkeypatch.setattr(research, "read_repo_files", lambda *args, **kwargs: [("a.py", "print('x')")])
    monkeypatch.setattr(
        research,
        "build_runtime",
        lambda **kwargs: (
            Settings("openai", "gpt-4o-mini", "openai", "text-embedding-3-small", 3, 200, 20, str(tmp_path / ".cache")),
            object(),
        ),
    )

    class _FakeEngine:
        def __init__(self, provider) -> None:
            self.counter = 0

        async def answer(self, **kwargs):
            self.counter += 1
            idx = self.counter
            return AskResult(
                answer=f"finding-{idx}\nWhat next?",
                sources=[AnswerSource(file_path="a.py", chunk_preview="x", relevance_score=0.6 + idx * 0.1)],
                metadata={"index_cached": idx > 1},
            )

    monkeypatch.setattr(research, "RAGEngine", _FakeEngine)

    runner = CliRunner()
    app = _app()

    result_json = runner.invoke(app, [str(repo), "cache-strategy", "-n", "2", "--json"])
    assert result_json.exit_code == 0
    payload = json.loads(result_json.stdout.strip())
    assert payload["type"] == "research"
    assert payload["data"]["topic"] == "cache-strategy"
    assert len(payload["data"]["iterations"]) == 2
    assert payload["metadata"]["iterations_completed"] == 2
    assert payload["metadata"]["index_cached"] is True

    result_plain = runner.invoke(app, [str(repo), "indexing", "-n", "1"])
    assert result_plain.exit_code == 0
    assert "Topic: indexing" in result_plain.stdout
    assert "Conclusion:" in result_plain.stdout
    assert "Sources:" in result_plain.stdout
