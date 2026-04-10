from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import asdict
from pathlib import Path

import typer

from deepwiki.cli.callbacks import build_runtime
from deepwiki.core.models import WikiPage, WikiResult
from deepwiki.core.wiki_generator import WikiGenerator
from deepwiki.data.document_reader import read_repo_files
from deepwiki.data.repo_manager import resolve_repo_path
from deepwiki.output.safe_display import display_repo_ref


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    cleaned = re.sub(r"[\s_-]+", "-", cleaned)
    return cleaned or "page"


def _markdown_readme(result: WikiResult) -> str:
    lines = [f"# {result.title}", "", "## Contents", ""]
    for index, page in enumerate(result.pages, start=1):
        filename = f"{index:02d}-{_slugify(page.title)}.md"
        lines.append(f"- [{page.title}]({filename})")
    lines.append("")
    return "\n".join(lines)


def _write_markdown_export(output_dir: Path, result: WikiResult, metadata: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text(_markdown_readme(result), encoding="utf-8")
    for index, page in enumerate(result.pages, start=1):
        filename = f"{index:02d}-{_slugify(page.title)}.md"
        content = page.content if page.content.strip() else "(empty)"
        (output_dir / filename).write_text(content + "\n", encoding="utf-8")
    diagrams_dir = output_dir / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")


def _write_json_export(output_dir: Path, result: WikiResult, metadata: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "success",
        "type": "wiki",
        "data": {
            "title": result.title,
            "pages": [asdict(page) for page in result.pages],
        },
        "metadata": metadata,
    }
    (output_dir / "wiki.json").write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _offline_wiki(repo_path: Path, files: list[tuple[str, str]]) -> WikiResult:
    summary_lines = [path for path, _ in files]
    body = "\n".join(summary_lines) if summary_lines else "(no readable files)"
    content = f"```text\n{body}\n```"
    return WikiResult(title=f"Wiki for {repo_path.name}", pages=[WikiPage(title="Repository Overview (offline)", content=content)])


def register_export(app: typer.Typer) -> None:
    @app.command("export")
    def export(
        repo: str = typer.Argument(..., help="Repository path or remote URL"),
        format: str = typer.Option("markdown", "--format", help="Export format: markdown or json"),
        output_dir: str = typer.Option("./exports", "--output-dir", "-o", help="Output directory"),
        language: str = typer.Option("en", "--language", "-l", help="Output language"),
        token: str | None = typer.Option(None, "--token", help="Access token for private remote repositories"),
        repo_type: str | None = typer.Option(None, "--repo-type", help="Repository type: github, gitlab, bitbucket"),
        provider: str | None = typer.Option(None, "--provider", "-p", help="LLM provider override"),
        model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
        offline: bool = typer.Option(False, "--offline", help="Skip LLM call and export local file summary"),
    ) -> None:
        started = time.perf_counter()
        selected_format = format.strip().lower()
        if selected_format not in {"markdown", "json"}:
            raise typer.BadParameter("format must be one of: markdown, json")

        repo_path = resolve_repo_path(repo, token=token, repo_type=repo_type)
        output_path = Path(output_dir).expanduser().resolve()
        settings, runtime_provider = build_runtime(provider=provider, model=model, project_root=repo_path)
        files = read_repo_files(repo_path)

        if offline:
            result = _offline_wiki(repo_path, files)
        else:
            generator = WikiGenerator(
                provider=runtime_provider,
                provider_name=settings.provider,
                model_name=settings.model,
            )
            result = asyncio.run(generator.generate(repo_name=repo_path.name, files=files))

        metadata = {
            "repo": display_repo_ref(repo_path),
            "language": language,
            "format": selected_format,
            "pages_generated": len(result.pages),
            "provider": settings.provider,
            "model": settings.model,
            "offline": offline,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

        if selected_format == "markdown":
            _write_markdown_export(output_path, result, metadata)
        else:
            _write_json_export(output_path, result, metadata)

        typer.echo(f"Export completed: {selected_format}")
        typer.echo(f"Output: {output_path}")
