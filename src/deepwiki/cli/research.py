from __future__ import annotations

import asyncio
import time
from collections import OrderedDict

import typer

from deepwiki.cli.callbacks import build_runtime
from deepwiki.core.models import AskResult, ResearchIteration, ResearchResult
from deepwiki.core.rag_engine import RAGEngine
from deepwiki.data.document_reader import read_repo_files
from deepwiki.data.repo_manager import resolve_repo_path
from deepwiki.output.json_output import JSONFormatter


def _build_iteration_question(topic: str, prior_findings: list[str], index: int) -> str:
    if index == 0:
        return f"Research topic: {topic}. Provide key findings with concrete file references and risks."

    previous = prior_findings[-1] if prior_findings else ""
    snippet = previous[:800]
    return (
        f"Continue researching topic: {topic}. "
        "Based on previous findings below, dive deeper into unresolved parts, implementation trade-offs, "
        "and concrete next actions.\n\n"
        f"Previous findings:\n{snippet}"
    )


def _extract_follow_ups(findings: str) -> list[str]:
    lines = [line.strip("- ").strip() for line in findings.splitlines()]
    candidates: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.endswith("?"):
            candidates.append(line)
        if len(candidates) == 3:
            break
    if candidates:
        return candidates
    return ["What repository area should be inspected next to validate this conclusion?"]


def _dedupe_sources(results: list[AskResult]) -> list:
    merged: OrderedDict[tuple[str, str], object] = OrderedDict()
    for result in results:
        for source in result.sources:
            key = (source.file_path, source.chunk_preview)
            existing = merged.get(key)
            if existing is None or source.relevance_score > existing.relevance_score:
                merged[key] = source
    return list(merged.values())


def register_research(app: typer.Typer) -> None:
    @app.command("research")
    def research(
        repo: str = typer.Argument(..., help="Repository path"),
        topic: str = typer.Argument(..., help="Research topic about the repository"),
        iterations: int = typer.Option(3, "--iterations", "-n", min=1, help="Research iterations"),
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
        started = time.perf_counter()
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

        ask_results: list[AskResult] = []
        research_iterations: list[ResearchIteration] = []
        findings_history: list[str] = []

        for idx in range(iterations):
            question = _build_iteration_question(topic=topic, prior_findings=findings_history, index=idx)
            ask_result = asyncio.run(
                engine.answer(
                    repo_path=repo_path,
                    files=files,
                    question=question,
                    settings=settings,
                    top_k=top_k,
                    use_cache=not no_cache,
                )
            )
            ask_results.append(ask_result)
            findings_history.append(ask_result.answer)
            follow_ups = _extract_follow_ups(ask_result.answer)
            research_iterations.append(
                ResearchIteration(
                    iteration=idx + 1,
                    question=question,
                    findings=ask_result.answer,
                    follow_up_questions=follow_ups,
                )
            )

        summary = findings_history[0] if findings_history else ""
        conclusion = findings_history[-1] if findings_history else ""
        sources = _dedupe_sources(ask_results)

        metadata = {
            "repo": str(repo_path.resolve()),
            "iterations_completed": len(research_iterations),
            "provider": settings.provider,
            "model": settings.model,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "index_cached": all(bool(result.metadata.get("index_cached", False)) for result in ask_results[1:])
            if len(ask_results) > 1
            else bool(ask_results[0].metadata.get("index_cached", False)) if ask_results else False,
        }

        research_result = ResearchResult(
            topic=topic,
            summary=summary,
            iterations=research_iterations,
            conclusion=conclusion,
            sources=sources,
            metadata=metadata,
        )

        formatter = JSONFormatter()
        if json_output:
            formatter.render_research(research_result)
            return

        typer.echo(f"Topic: {research_result.topic}")
        for item in research_result.iterations:
            typer.echo("")
            typer.echo(f"Iteration {item.iteration}")
            typer.echo(f"Question: {item.question}")
            typer.echo(item.findings)
            if item.follow_up_questions:
                typer.echo("Follow-ups:")
                for follow_up in item.follow_up_questions:
                    typer.echo(f"- {follow_up}")

        typer.echo("")
        typer.echo("Conclusion:")
        typer.echo(research_result.conclusion)

        if research_result.sources:
            typer.echo("")
            typer.echo("Sources:")
            for source in research_result.sources:
                typer.echo(f"- {source.file_path} ({source.relevance_score:.3f})")
