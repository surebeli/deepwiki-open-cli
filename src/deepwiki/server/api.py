from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from deepwiki.cli.callbacks import build_runtime
from deepwiki.core.models import AskResult, ResearchIteration, ResearchResult, WikiPage, WikiResult
from deepwiki.providers.base import CompletionRequest, EmbeddingRequest
from deepwiki.core.rag_engine import RAGEngine
from deepwiki.core.wiki_generator import WikiGenerator
from deepwiki.data.document_reader import read_repo_files
from deepwiki.data.repo_manager import resolve_repo_path
from deepwiki.config.providers_catalog import load_provider_catalogs
from deepwiki.output.safe_display import display_repo_ref


class AskRequest(BaseModel):
    repo: str | None = None
    repo_url: str | None = None
    question: str | None = None
    messages: list[dict[str, str]] | None = None
    token: str | None = None
    repo_type: str | None = None
    provider: str | None = None
    model: str | None = None
    embed_provider: str | None = None
    embed_model: str | None = None
    top_k: int | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    cache_dir: str | None = None
    no_cache: bool = False

def _extract_question(request: AskRequest) -> str:
    if request.question:
        return request.question
    if request.messages and len(request.messages) > 0:
        return request.messages[-1].get("content", "")
    return ""


class GenerateRequest(BaseModel):
    repo: str | None = None
    repo_url: str | None = None
    token: str | None = None
    repo_type: str | None = None
    provider: str | None = None
    model: str | None = None
    offline: bool = False


class ResearchRequest(BaseModel):
    repo: str | None = None
    repo_url: str | None = None
    topic: str
    iterations: int = 3
    token: str | None = None
    repo_type: str | None = None
    provider: str | None = None
    model: str | None = None
    embed_provider: str | None = None
    embed_model: str | None = None
    top_k: int | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    cache_dir: str | None = None
    no_cache: bool = False


def _resolve_repo_input(repo: str | None, repo_url: str | None) -> str:
    candidate = repo or repo_url
    if not candidate:
        raise ValueError("repo or repo_url is required")
    return candidate


def _offline_wiki(repo_path: Path, files: list[tuple[str, str]]) -> WikiResult:
    summary_lines = [path for path, _ in files]
    body = "\n".join(summary_lines) if summary_lines else "(no readable files)"
    content = f"```text\n{body}\n```"
    return WikiResult(title=f"Wiki for {repo_path.name}", pages=[WikiPage(title="Repository Overview (offline)", content=content)])


def _build_iteration_question(topic: str, prior_findings: list[str], index: int) -> str:
    if index == 0:
        return f"Research topic: {topic}. Provide key findings with concrete file references and risks."
    previous = prior_findings[-1] if prior_findings else ""
    snippet = previous[:800]
    return (
        f"Continue researching topic: {topic}. "
        "Based on previous findings below, dive deeper into unresolved parts, implementation trade-offs, and concrete next actions.\n\n"
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


def create_app(cors_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(title="DeepWiki API", version="0.2.10")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # Allow all origins for local dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "success", "type": "health", "data": {"ok": True}, "metadata": {}}

    @app.get("/auth/status")
    @app.get("/api/auth/status")
    def auth_status() -> dict[str, object]:
        return {
            "status": "success",
            "success": True,
            "auth_required": False
        }

    @app.post("/auth/validate")
    @app.post("/api/auth/validate")
    def auth_validate() -> dict[str, object]:
        return {
            "status": "success",
            "success": True,
            "valid": True
        }

    @app.get("/models/config")
    @app.get("/api/models/config")
    def models_config_endpoint() -> dict[str, object]:
        return models_config()

    @app.get("/lang/config")
    def lang_config() -> dict[str, object]:
        return {
            "status": "success",
            "default": "en",
            "supported_languages": {
                "en": "English",
                "ja": "Japanese (日本語)",
                "zh": "Mandarin Chinese (中文)",
                "zh-tw": "Traditional Chinese (繁體中文)",
                "es": "Spanish (Español)",
                "kr": "Korean (한국어)",
                "vi": "Vietnamese (Tiếng Việt)",
                "pt-br": "Brazilian Portuguese (Português Brasileiro)",
                "fr": "Français (French)",
                "ru": "Русский (Russian)"
            }
        }

    @app.get("/api/processed_projects")
    def processed_projects() -> dict[str, object]:
        return {"status": "success", "data": []}

    @app.get("/models/config")
    def models_config_root() -> dict[str, object]:
        return models_config()

    @app.get("/api/wiki_cache")
    def get_wiki_cache(repo: str, language: str = "en") -> dict[str, object]:
        try:
            repo_path = resolve_repo_path(repo)
            # Find generated wiki files in cache
            settings, _ = build_runtime(project_root=repo_path)
            from deepwiki.data.cache_manager import CacheManager
            cache_manager = CacheManager(settings.cache_dir)
            
            # This is a bit simplified, but let's try to find a wiki result
            # Ideally we'd have a specific metadata store for generated wikis
            return {"status": "error", "message": "Cache lookup not fully implemented, please click Generate"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.get("/local_repo/structure")
    def local_repo_structure(path: str) -> dict[str, object]:
        print(f"Fetching structure for local path: {path}")
        try:
            repo_path = Path(path).expanduser().resolve()
            if not repo_path.exists() or not repo_path.is_dir():
                return {"status": "error", "message": f"Directory not found: {path}"}
            
            from deepwiki.data.document_reader import read_repo_files
            files = read_repo_files(repo_path, limit=500)
            file_tree = "\n".join([f[0] for f in files])
            
            # Try to find README
            readme = ""
            for name in ["README.md", "README", "readme.md"]:
                readme_path = repo_path / name
                if readme_path.exists():
                    readme = readme_path.read_text(encoding="utf-8", errors="ignore")
                    break

            return {
                "status": "success",
                "file_tree": file_tree,
                "readme": readme,
                "data": {
                    "name": repo_path.name,
                    "path": str(repo_path),
                    "is_local": True
                }
            }
        except Exception as exc:
            print(f"Error in local_repo_structure: {exc}")
            return {"status": "error", "message": str(exc)}

    @app.post("/api/wiki_cache")
    def create_wiki_cache(request: GenerateRequest) -> dict[str, object]:
        # Alias for generate
        return generate(request)

    @app.get("/api/models/config")
    def models_config() -> dict[str, object]:
        generator_catalog, _ = load_provider_catalogs()
        providers = []
        for p_id, models in generator_catalog.items():
            providers.append({
                "id": p_id,
                "name": p_id.capitalize(),
                "models": [{"id": m, "name": m} for m in models],
                "supportsCustomModel": True
            })
        
        return {
            "providers": providers,
            "defaultProvider": "ollama" if "ollama" in generator_catalog else (providers[0]["id"] if providers else "")
        }

    @app.post("/api/chat/stream")
    async def chat_stream_api(request: AskRequest):
        from fastapi.responses import StreamingResponse
        return await chat_stream_internal(request)

    @app.post("/chat/completions/stream")
    async def chat_stream_completions(request: AskRequest):
        return await chat_stream_internal(request)

    async def chat_stream_internal(request: AskRequest):
        from fastapi.responses import StreamingResponse
        try:
            repo_input = _resolve_repo_input(request.repo, request.repo_url)
            repo_path = resolve_repo_path(repo_input, token=request.token, repo_type=request.repo_type)
            settings, runtime_provider = build_runtime(
                provider=request.provider,
                model=request.model,
                project_root=repo_path,
            )
            
            question = _extract_question(request)
            async def event_generator():
                async for chunk in runtime_provider.stream(
                    CompletionRequest(
                        prompt=question,
                        model=settings.model,
                        provider=settings.provider,
                    )
                ):
                    yield chunk

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    from fastapi import WebSocket, WebSocketDisconnect
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                request = AskRequest(**data)
                
                repo_input = _resolve_repo_input(request.repo, request.repo_url)
                repo_path = resolve_repo_path(repo_input, token=request.token, repo_type=request.repo_type)
                settings, runtime_provider = build_runtime(
                    provider=request.provider,
                    model=request.model,
                    project_root=repo_path,
                )
                
                question = _extract_question(request)
                async for chunk in runtime_provider.stream(
                    CompletionRequest(
                        prompt=question,
                        model=settings.model,
                        provider=settings.provider,
                    )
                ):
                    await websocket.send_text(chunk)
                
                await websocket.close()
                break
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            print(f"WebSocket error: {exc}")
            try:
                await websocket.send_text(f"Error: {exc}")
                await websocket.close()
            except:
                pass

    @app.get("/api/providers")
    def providers() -> dict[str, object]:
        generator_catalog, embedder_catalog = load_provider_catalogs()
        return {
            "status": "success",
            "type": "providers",
            "data": {"generator": generator_catalog, "embedder": embedder_catalog},
            "metadata": {},
        }

    @app.get("/api/models/{provider}")
    def models(provider: str) -> dict[str, object]:
        generator_catalog, embedder_catalog = load_provider_catalogs()
        models_value = generator_catalog.get(provider, [])
        embed_models = embedder_catalog.get(provider, [])
        return {
            "status": "success",
            "type": "models",
            "data": {"provider": provider, "models": models_value, "embed_models": embed_models},
            "metadata": {},
        }

    @app.post("/api/generate")
    def generate(request: GenerateRequest) -> dict[str, object]:
        try:
            repo_input = _resolve_repo_input(request.repo, request.repo_url)
            repo_path = resolve_repo_path(repo_input, token=request.token, repo_type=request.repo_type)
            settings, runtime_provider = build_runtime(
                provider=request.provider,
                model=request.model,
                project_root=repo_path,
            )
            files = read_repo_files(repo_path)
            if request.offline:
                result = _offline_wiki(repo_path, files)
            else:
                generator = WikiGenerator(
                    provider=runtime_provider,
                    provider_name=settings.provider,
                    model_name=settings.model,
                )
                result = asyncio.run(generator.generate(repo_name=repo_path.name, files=files))
            return {
                "status": "success",
                "type": "wiki",
                "data": {"title": result.title, "pages": [asdict(page) for page in result.pages]},
                "metadata": {"repo": display_repo_ref(repo_path), "provider": settings.provider, "model": settings.model},
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ask")
    def ask(request: AskRequest) -> dict[str, object]:
        try:
            repo_input = _resolve_repo_input(request.repo, request.repo_url)
            repo_path = resolve_repo_path(repo_input, token=request.token, repo_type=request.repo_type)
            settings, runtime_provider = build_runtime(
                provider=request.provider,
                model=request.model,
                embed_provider=request.embed_provider,
                embed_model=request.embed_model,
                top_k=request.top_k,
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                cache_dir=request.cache_dir,
                project_root=repo_path,
            )
            files = read_repo_files(repo_path, limit=500)
            engine = RAGEngine(provider=runtime_provider)
            question = _extract_question(request)
            result = asyncio.run(
                engine.answer(
                    repo_path=repo_path,
                    files=files,
                    question=question,
                    settings=settings,
                    top_k=request.top_k,
                    use_cache=not request.no_cache,
                )
            )
            return {
                "status": "success",
                "type": "answer",
                "data": {
                    "answer": result.answer,
                    "sources": [asdict(source) for source in result.sources],
                },
                "metadata": result.metadata,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/research")
    def research(request: ResearchRequest) -> dict[str, object]:
        try:
            started = time.perf_counter()
            repo_input = _resolve_repo_input(request.repo, request.repo_url)
            repo_path = resolve_repo_path(repo_input, token=request.token, repo_type=request.repo_type)
            settings, runtime_provider = build_runtime(
                provider=request.provider,
                model=request.model,
                embed_provider=request.embed_provider,
                embed_model=request.embed_model,
                top_k=request.top_k,
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                cache_dir=request.cache_dir,
                project_root=repo_path,
            )
            files = read_repo_files(repo_path, limit=500)
            engine = RAGEngine(provider=runtime_provider)

            ask_results: list[AskResult] = []
            research_iterations: list[ResearchIteration] = []
            findings_history: list[str] = []
            for idx in range(max(1, request.iterations)):
                question = _build_iteration_question(topic=request.topic, prior_findings=findings_history, index=idx)
                ask_result = asyncio.run(
                    engine.answer(
                        repo_path=repo_path,
                        files=files,
                        question=question,
                        settings=settings,
                        top_k=request.top_k,
                        use_cache=not request.no_cache,
                    )
                )
                ask_results.append(ask_result)
                findings_history.append(ask_result.answer)
                research_iterations.append(
                    ResearchIteration(
                        iteration=idx + 1,
                        question=question,
                        findings=ask_result.answer,
                        follow_up_questions=_extract_follow_ups(ask_result.answer),
                    )
                )

            result = ResearchResult(
                topic=request.topic,
                summary=findings_history[0] if findings_history else "",
                iterations=research_iterations,
                conclusion=findings_history[-1] if findings_history else "",
                sources=_dedupe_sources(ask_results),
                metadata={
                    "repo": display_repo_ref(repo_path),
                    "iterations_completed": len(research_iterations),
                    "provider": settings.provider,
                    "model": settings.model,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            return {
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
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
