import asyncio

import typer

from deepwiki.cli.callbacks import build_runtime
from deepwiki.core.models import WikiPage, WikiResult
from deepwiki.core.wiki_generator import WikiGenerator
from deepwiki.data.document_reader import read_repo_files
from deepwiki.data.repo_manager import resolve_repo_path
from deepwiki.output.terminal import TerminalFormatter


def register_generate(app: typer.Typer) -> None:
    @app.command("generate")
    def generate(
        repo: str = typer.Argument(..., help="Repository path"),
        provider: str | None = typer.Option(None, "--provider", "-p", help="LLM provider override"),
        model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
        token: str | None = typer.Option(None, "--token", help="Access token for private remote repositories"),
        repo_type: str | None = typer.Option(None, "--repo-type", help="Repository type: github, gitlab, bitbucket"),
        offline: bool = typer.Option(False, "--offline", help="Skip LLM call and render local file summary"),
    ) -> None:
        repo_path = resolve_repo_path(repo, token=token, repo_type=repo_type)
        settings, runtime_provider = build_runtime(provider, model, project_root=repo_path)
        files = read_repo_files(repo_path)

        if offline:
            summary_lines = [path for path, _ in files]
            body = "\n".join(summary_lines) if summary_lines else "(no readable files)"
            content = f"```text\n{body}\n```"
            result = WikiResult(
                title=f"Wiki for {repo_path.name}",
                pages=[WikiPage(title="Repository Overview (offline)", content=content)],
            )
        else:
            generator = WikiGenerator(
                provider=runtime_provider,
                provider_name=settings.provider,
                model_name=settings.model,
            )
            result = asyncio.run(generator.generate(repo_name=repo_path.name, files=files))

        TerminalFormatter().render(result)
