from __future__ import annotations

import importlib
import runpy

import typer
from typer.testing import CliRunner

from deepwiki.cli import serve
from deepwiki.core.wiki_generator import WikiGenerator


def test_main_module_invokes_cli_main(monkeypatch) -> None:
    app_module = importlib.import_module("deepwiki.cli.app")
    called = {"ok": False}
    monkeypatch.setattr(app_module, "main", lambda: called.update({"ok": True}))
    runpy.run_module("deepwiki.__main__", run_name="__main__")
    assert called["ok"] is True


def test_serve_command_invokes_uvicorn(monkeypatch) -> None:
    called = {}
    monkeypatch.setattr(serve, "create_app", lambda cors_origins: {"origins": cors_origins})
    monkeypatch.setattr(
        serve.uvicorn,
        "run",
        lambda app, host, port, reload: called.update(
            {"app": app, "host": host, "port": port, "reload": reload}
        ),
    )
    app = typer.Typer()
    serve.register_serve(app)
    result = CliRunner().invoke(
        app, ["--host", "127.0.0.1", "--port", "9000", "--reload", "--cors-origins", "https://a.com,https://b.com"]
    )
    assert result.exit_code == 0
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 9000
    assert called["reload"] is True
    assert called["app"]["origins"] == ["https://a.com", "https://b.com"]


def test_wiki_generator_and_formatter_module_import() -> None:
    class _Provider:
        async def complete(self, request):
            from deepwiki.providers.base import CompletionResponse

            return CompletionResponse(content="wiki-content", model=request.model, provider=request.provider)

    import asyncio

    generator = WikiGenerator(provider=_Provider(), provider_name="openai", model_name="m")
    result = asyncio.run(generator.generate("repo", [("a.py", "x")]))
    assert result.title == "Wiki for repo"
    assert result.pages[0].content == "wiki-content"

    formatter = importlib.import_module("deepwiki.output.formatter")
    assert hasattr(formatter, "OutputFormatter")
