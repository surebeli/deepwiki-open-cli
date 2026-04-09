from __future__ import annotations

from pathlib import Path

import typer

from deepwiki.cli.ask import run_ask_turn
from deepwiki.cli.callbacks import build_runtime
from deepwiki.core.rag_engine import RAGEngine
from deepwiki.data.document_reader import read_repo_files
from deepwiki.data.repo_manager import resolve_repo_path


def _print_help() -> None:
    typer.echo("Commands:")
    typer.echo("  /help         Show REPL help")
    typer.echo("  /clear        Clear in-memory session history")
    typer.echo("  /exit, /quit  Exit REPL")


def _render_answer(answer: str, sources: list[object]) -> None:
    typer.echo(answer)
    if sources:
        typer.echo("")
        typer.echo("Sources:")
        for source in sources:
            typer.echo(f"- {source.file_path} ({source.relevance_score:.3f})")


def register_repl(app: typer.Typer) -> None:
    @app.command("repl")
    def repl(
        repo: str = typer.Argument(..., help="Repository path"),
        token: str | None = typer.Option(None, "--token", help="Access token for private remote repositories"),
        repo_type: str | None = typer.Option(None, "--repo-type", help="Repository type: github, gitlab, bitbucket"),
        provider: str | None = typer.Option(None, "--provider", "-p", help="LLM provider override"),
        model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
        embed_provider: str | None = typer.Option(None, "--embed-provider", help="Embedding provider override"),
        embed_model: str | None = typer.Option(None, "--embed-model", help="Embedding model override"),
        top_k: int | None = typer.Option(None, "--top-k", help="Retrieved chunk count"),
        chunk_size: int | None = typer.Option(None, "--chunk-size", help="Chunk size for indexing"),
        chunk_overlap: int | None = typer.Option(None, "--chunk-overlap", help="Chunk overlap for indexing"),
        cache_dir: str | None = typer.Option(None, "--cache-dir", help="Cache directory override"),
        no_cache: bool = typer.Option(False, "--no-cache", help="Skip index cache reuse"),
    ) -> None:
        repo_path = resolve_repo_path(repo, token=token, repo_type=repo_type)
        settings, runtime_provider = build_runtime(
            provider=provider,
            model=model,
            embed_provider=embed_provider,
            embed_model=embed_model,
            top_k=top_k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            cache_dir=cache_dir,
            project_root=repo_path,
        )

        files = read_repo_files(repo_path, limit=500)
        engine = RAGEngine(provider=runtime_provider)
        history: list[tuple[str, str]] = []

        typer.echo(f"DeepWiki REPL for {Path(repo_path).name}")
        typer.echo("Type /help for commands. Ctrl+D also exits.")

        while True:
            try:
                raw = input("deepwiki> ").strip()
            except EOFError:
                typer.echo("")
                break
            except KeyboardInterrupt:
                typer.echo("")
                break

            if not raw:
                continue

            lowered = raw.lower()
            if lowered in {"/exit", "/quit", "exit", "quit"}:
                break
            if lowered in {"/help", "help"}:
                _print_help()
                continue
            if lowered == "/clear":
                history.clear()
                typer.echo("Session history cleared.")
                continue

            try:
                result = run_ask_turn(
                    engine=engine,
                    repo_path=repo_path,
                    files=files,
                    question=raw,
                    settings=settings,
                    top_k=top_k,
                    use_cache=not no_cache,
                )
            except Exception as exc:
                typer.echo(f"Error: {exc}", err=True)
                continue

            history.append((raw, result.answer))
            _render_answer(result.answer, result.sources)
            typer.echo("")
