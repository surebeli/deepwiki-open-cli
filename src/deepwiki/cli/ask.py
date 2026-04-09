from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from deepwiki.cli.callbacks import build_runtime
from deepwiki.config.settings import Settings
from deepwiki.core.models import AskResult
from deepwiki.core.rag_engine import RAGEngine
from deepwiki.data.document_reader import read_repo_files
from deepwiki.data.repo_manager import resolve_repo_path
from deepwiki.output.json_output import JSONFormatter


def run_ask_turn(
    engine: RAGEngine,
    repo_path: Path,
    files: list[tuple[str, str]],
    question: str,
    settings: Settings,
    top_k: int | None,
    use_cache: bool,
) -> AskResult:
    return asyncio.run(
        engine.answer(
            repo_path=repo_path,
            files=files,
            question=question,
            settings=settings,
            top_k=top_k,
            use_cache=use_cache,
        )
    )


def register_ask(app: typer.Typer) -> None:
    @app.command("ask")
    def ask(
        repo: str = typer.Argument(..., help="Repository path"),
        question: str = typer.Argument(..., help="Question about the repository"),
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
        json_output: bool = typer.Option(False, "--json", help="Render JSON envelope output"),
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
        result = run_ask_turn(
            engine=engine,
            repo_path=repo_path,
            files=files,
            question=question,
            settings=settings,
            top_k=top_k,
            use_cache=not no_cache,
        )

        if json_output:
            JSONFormatter().render_answer(result)
            return

        typer.echo(result.answer)
        if result.sources:
            typer.echo("")
            typer.echo("Sources:")
            for source in result.sources:
                typer.echo(f"- {source.file_path} ({source.relevance_score:.3f})")
