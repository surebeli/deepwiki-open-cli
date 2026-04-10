from __future__ import annotations

import json
from pathlib import Path
from dataclasses import asdict

from deepwiki.config.settings import ResolvedSettings
from deepwiki.core.models import AskResult, ResearchResult
from deepwiki.output.safe_display import display_project_root


class JSONFormatter:
    @staticmethod
    def _mask_value(key: str, value: object) -> object:
        lowered = key.lower()
        if not isinstance(value, str):
            return value
        if not any(token in lowered for token in ("key", "token", "secret", "password")):
            return value
        if len(value) <= 8:
            return "****"
        return f"{value[:4]}****{value[-4:]}"

    def render_answer(self, result: AskResult) -> None:
        payload = {
            "status": "success",
            "type": "answer",
            "data": {
                "answer": result.answer,
                "sources": [asdict(source) for source in result.sources],
            },
            "metadata": result.metadata,
        }
        print(json.dumps(payload, ensure_ascii=True))

    def render_config(self, resolved: ResolvedSettings, project_root: Path) -> None:
        effective = {
            key: self._mask_value(key, value)
            for key, value in resolved.settings.__dict__.items()
        }
        sources = {
            key: {
                "source": value.source,
                "origin": value.origin,
            }
            for key, value in resolved.sources.items()
        }

        payload = {
            "status": "success",
            "type": "config",
            "data": {
                "effective": effective,
                "sources": sources,
            },
            "metadata": {
                "project_root": display_project_root(project_root),
            },
        }
        print(json.dumps(payload, ensure_ascii=True))

    def render_providers(
        self,
        project_root: Path,
        active_provider: str,
        active_model: str,
        active_embed_provider: str,
        active_embed_model: str,
        generator_catalog: dict[str, list[str]],
        embedder_catalog: dict[str, list[str]],
    ) -> None:
        payload = {
            "status": "success",
            "type": "providers",
            "data": {
                "active": {
                    "provider": active_provider,
                    "model": active_model,
                    "embed_provider": active_embed_provider,
                    "embed_model": active_embed_model,
                },
                "generator": generator_catalog,
                "embedder": embedder_catalog,
            },
            "metadata": {
                "project_root": display_project_root(project_root),
            },
        }
        print(json.dumps(payload, ensure_ascii=True))

    def render_research(self, result: ResearchResult) -> None:
        payload = {
            "status": "success",
            "type": "research",
            "data": {
                "topic": result.topic,
                "summary": result.summary,
                "iterations": [asdict(iteration) for iteration in result.iterations],
                "conclusion": result.conclusion,
                "sources": [asdict(source) for source in result.sources],
            },
            "metadata": result.metadata,
        }
        print(json.dumps(payload, ensure_ascii=True))
