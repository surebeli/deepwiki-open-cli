from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml

from deepwiki.cli.callbacks import build_resolved_settings
from deepwiki.config.providers_catalog import load_provider_catalogs
from deepwiki.config.settings import project_config_path, user_config_path
from deepwiki.output.json_output import JSONFormatter
from deepwiki.output.safe_display import display_config_path, display_project_root

_INT_FIELDS = {"top_k", "chunk_size", "chunk_overlap"}
_SUPPORTED_FIELDS = (
    "provider",
    "model",
    "embed_provider",
    "embed_model",
    "top_k",
    "chunk_size",
    "chunk_overlap",
    "cache_dir",
)


def _resolve_project_root(repo: str | None) -> Path:
    if repo is None:
        return Path.cwd().resolve()

    candidate = Path(repo).resolve()
    if not candidate.exists() or not candidate.is_dir():
        raise typer.BadParameter(f"Repository path does not exist or is not a directory: {repo}")
    return candidate


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _coerce_value(key: str, value: str) -> str | int:
    if key in _INT_FIELDS:
        try:
            return int(value)
        except ValueError as exc:
            raise typer.BadParameter(f"{key} expects an integer value, got: {value}") from exc
    return value


def _read_config_file(path: Path) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_config_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dumped = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    path.write_text(dumped, encoding="utf-8")


def _scope_path(scope: str, project_root: Path) -> Path:
    if scope == "user":
        return user_config_path()
    return project_config_path(project_root)


def register_config(app: typer.Typer) -> None:
    config_app = typer.Typer(help="Configuration commands")

    def _models_with_active_marker(models: list[str], provider_name: str, active_provider: str, active_model: str) -> str:
        marked: list[str] = []
        active_found = False
        for model_name in models:
            if provider_name == active_provider and model_name == active_model:
                marked.append(f"{model_name} *")
                active_found = True
            else:
                marked.append(model_name)
        if provider_name == active_provider and not active_found:
            marked.append(f"{active_model} *")
        return ", ".join(marked)

    @config_app.command("show")
    def show(
        repo: str | None = typer.Argument(None, help="Optional project root for project config lookup"),
        provider: str | None = typer.Option(None, "--provider", "-p", help="LLM provider override"),
        model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
        embed_provider: str | None = typer.Option(None, "--embed-provider", help="Embedding provider override"),
        embed_model: str | None = typer.Option(None, "--embed-model", help="Embedding model override"),
        top_k: int | None = typer.Option(None, "--top-k", help="Retrieved chunk count"),
        chunk_size: int | None = typer.Option(None, "--chunk-size", help="Chunk size for indexing"),
        chunk_overlap: int | None = typer.Option(None, "--chunk-overlap", help="Chunk overlap for indexing"),
        cache_dir: str | None = typer.Option(None, "--cache-dir", help="Cache directory override"),
        json_output: bool = typer.Option(False, "--json", help="Render JSON envelope output"),
    ) -> None:
        project_root = _resolve_project_root(repo)
        resolved = build_resolved_settings(
            provider=provider,
            model=model,
            embed_provider=embed_provider,
            embed_model=embed_model,
            top_k=top_k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            cache_dir=cache_dir,
            project_root=project_root,
        )

        formatter = JSONFormatter()
        if json_output:
            formatter.render_config(resolved=resolved, project_root=project_root)
            return

        typer.echo(f"Project Root: {display_project_root(project_root)}")
        for field in (
            "provider",
            "model",
            "embed_provider",
            "embed_model",
            "top_k",
            "chunk_size",
            "chunk_overlap",
            "cache_dir",
        ):
            value = getattr(resolved.settings, field)
            masked = formatter._mask_value(field, value)
            source = resolved.sources[field]
            typer.echo(f"{field}: {masked} (from: {source.source}; origin: {source.origin})")

    @config_app.command("providers")
    def providers(
        repo: str | None = typer.Argument(None, help="Optional project root for project config lookup"),
        json_output: bool = typer.Option(False, "--json", help="Render JSON envelope output"),
    ) -> None:
        project_root = _resolve_project_root(repo)
        resolved = build_resolved_settings(project_root=project_root)
        generator_catalog, embedder_catalog = load_provider_catalogs()

        formatter = JSONFormatter()
        if json_output:
            formatter.render_providers(
                project_root=project_root,
                active_provider=resolved.settings.provider,
                active_model=resolved.settings.model,
                active_embed_provider=resolved.settings.embed_provider,
                active_embed_model=resolved.settings.embed_model,
                generator_catalog=generator_catalog,
                embedder_catalog=embedder_catalog,
            )
            return

        typer.echo(f"Project Root: {display_project_root(project_root)}")
        typer.echo("Generation Providers:")
        for provider_name, models in generator_catalog.items():
            suffix = " *" if provider_name == resolved.settings.provider else ""
            typer.echo(f"- {provider_name}{suffix}")
            typer.echo(
                f"  models: {_models_with_active_marker(models, provider_name, resolved.settings.provider, resolved.settings.model)}"
            )

        typer.echo("")
        typer.echo("Embedding Providers:")
        for provider_name, models in embedder_catalog.items():
            suffix = " *" if provider_name == resolved.settings.embed_provider else ""
            typer.echo(f"- {provider_name}{suffix}")
            typer.echo(
                "  models: "
                + _models_with_active_marker(
                    models,
                    provider_name,
                    resolved.settings.embed_provider,
                    resolved.settings.embed_model,
                )
            )

        typer.echo("")
        typer.echo("* indicates effective settings")

    @config_app.command("set")
    def set_config(
        key: str = typer.Argument(..., help="Configuration key"),
        value: str = typer.Argument(..., help="Configuration value"),
        repo: str | None = typer.Argument(None, help="Optional project root for project config lookup"),
        scope: str = typer.Option("user", "--scope", help="Write target: user or project"),
        json_output: bool = typer.Option(False, "--json", help="Render JSON envelope output"),
    ) -> None:
        normalized_scope = scope.strip().lower()
        if normalized_scope not in {"user", "project"}:
            raise typer.BadParameter("scope must be one of: user, project")

        normalized_key = _normalize_key(key)
        if normalized_key not in _SUPPORTED_FIELDS:
            raise typer.BadParameter(f"Unsupported key: {key}. Supported keys: {', '.join(_SUPPORTED_FIELDS)}")

        project_root = _resolve_project_root(repo)
        target_path = _scope_path(normalized_scope, project_root)
        payload = _read_config_file(target_path)
        payload[normalized_key] = _coerce_value(normalized_key, value)
        _write_config_file(target_path, payload)

        resolved = build_resolved_settings(project_root=project_root)
        effective_value = getattr(resolved.settings, normalized_key)

        result = {
            "status": "success",
            "type": "config_set",
            "data": {
                "scope": normalized_scope,
                "path": display_config_path(target_path),
                "key": normalized_key,
                "written_value": payload[normalized_key],
                "effective_value": effective_value,
            },
            "metadata": {
                "project_root": display_project_root(project_root),
            },
        }
        if json_output:
            print(json.dumps(result, ensure_ascii=True))
            return

        typer.echo(f"Updated {normalized_key} in {display_config_path(target_path)}")
        typer.echo(f"effective: {effective_value}")

    @config_app.command("init")
    def init_config(
        repo: str | None = typer.Argument(None, help="Optional project root for project config lookup"),
        scope: str = typer.Option("user", "--scope", help="Write target: user or project"),
        json_output: bool = typer.Option(False, "--json", help="Render JSON envelope output"),
    ) -> None:
        normalized_scope = scope.strip().lower()
        if normalized_scope not in {"user", "project"}:
            raise typer.BadParameter("scope must be one of: user, project")

        project_root = _resolve_project_root(repo)
        target_path = _scope_path(normalized_scope, project_root)
        existing = _read_config_file(target_path)
        resolved = build_resolved_settings(project_root=project_root)

        provider = typer.prompt("Provider", default=str(existing.get("provider", resolved.settings.provider)))
        model = typer.prompt("Model", default=str(existing.get("model", resolved.settings.model)))
        embed_provider = typer.prompt(
            "Embed Provider", default=str(existing.get("embed_provider", resolved.settings.embed_provider))
        )
        embed_model = typer.prompt("Embed Model", default=str(existing.get("embed_model", resolved.settings.embed_model)))
        top_k = typer.prompt("Top K", type=int, default=int(existing.get("top_k", resolved.settings.top_k)))
        chunk_size = typer.prompt(
            "Chunk Size", type=int, default=int(existing.get("chunk_size", resolved.settings.chunk_size))
        )
        chunk_overlap = typer.prompt(
            "Chunk Overlap", type=int, default=int(existing.get("chunk_overlap", resolved.settings.chunk_overlap))
        )
        cache_dir = typer.prompt("Cache Dir", default=str(existing.get("cache_dir", resolved.settings.cache_dir)))

        payload = dict(existing)
        payload.update(
            {
                "provider": provider,
                "model": model,
                "embed_provider": embed_provider,
                "embed_model": embed_model,
                "top_k": int(top_k),
                "chunk_size": int(chunk_size),
                "chunk_overlap": int(chunk_overlap),
                "cache_dir": cache_dir,
            }
        )
        _write_config_file(target_path, payload)

        result = {
            "status": "success",
            "type": "config_init",
            "data": {
                "scope": normalized_scope,
                "path": display_config_path(target_path),
                "written_keys": list(_SUPPORTED_FIELDS),
            },
            "metadata": {
                "project_root": display_project_root(project_root),
            },
        }
        if json_output:
            print(json.dumps(result, ensure_ascii=True))
            return

        typer.echo(f"Initialized config at {display_config_path(target_path)}")

    @config_app.command("path")
    def config_path(
        repo: str | None = typer.Argument(None, help="Optional project root for project config lookup"),
        json_output: bool = typer.Option(False, "--json", help="Render JSON envelope output"),
    ) -> None:
        project_root = _resolve_project_root(repo)
        user_path = user_config_path()
        project_path = project_config_path(project_root)
        result = {
            "status": "success",
            "type": "config_path",
            "data": {
                "user": display_config_path(user_path),
                "project": display_config_path(project_path),
                "project_root": display_project_root(project_root),
            },
            "metadata": {
                "user_exists": user_path.exists(),
                "project_exists": project_path.exists(),
            },
        }
        if json_output:
            print(json.dumps(result, ensure_ascii=True))
            return

        typer.echo(f"user: {display_config_path(user_path)}")
        typer.echo(f"project: {display_config_path(project_path)}")
        typer.echo(f"project_root: {display_project_root(project_root)}")

    app.add_typer(config_app, name="config")
