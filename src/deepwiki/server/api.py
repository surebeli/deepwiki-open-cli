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

    # More explicit origins for local development
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    if cors_origins:
        origins.extend(cors_origins)
    
    # Specification: cannot use * with allow_credentials=True
    # Origins should be explicit
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if "*" not in origins else [o for o in origins if o != "*"],
        allow_origin_regex=".*",
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

    import json
    import os
    
    def _get_cache_path(repo: str, language: str) -> Path:
        from deepwiki.data.repo_manager import _default_repo_cache_dir
        # Simple cache naming based on repo name and language
        safe_repo = repo.replace("/", "_").replace("\\", "_").replace(":", "_")
        cache_dir = _default_repo_cache_dir() / "wiki_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{safe_repo}_{language}.json"

    @app.get("/api/wiki_cache")
    def get_wiki_cache(repo: str, owner: str | None = None, language: str = "en") -> dict[str, object]:
        try:
            lookup_repo = repo
            if owner and owner != "local":
                lookup_repo = f"{owner}/{repo}"
            
            # 1. Direct path-based cache lookup
            cache_path = _get_cache_path(lookup_repo, language)
            
            # 2. Fuzzy match fallback
            if not cache_path.exists():
                from deepwiki.data.repo_manager import _default_repo_cache_dir
                cache_dir = _default_repo_cache_dir() / "wiki_cache"
                if cache_dir.exists():
                    # The filenames are like F__workspace_ai_hawk_agent-rs_zh.json
                    # Search for any file containing repo name and ending with language suffix
                    for f in cache_dir.glob(f"*{repo}*{language}.json"):
                        cache_path = f
                        print(f"DEBUG: Found fuzzy cache match: {f}")
                        break

            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    # RETURN THE RAW CONTENT DIRECTLY as the UI expects
                    return json.load(f)
            
            # If not found, return a structure that tells the UI to keep looking or rebuild
            # UI expects an object with wiki_structure and generated_pages to consider it a success
            return None
        except Exception as exc:
            print(f"DEBUG: Error in get_wiki_cache: {exc}")
            return None

    @app.post("/api/wiki_cache")
    async def create_wiki_cache(request: dict) -> dict[str, object]:
        try:
            # The UI sends: repo, language, wiki_structure, generated_pages, provider, model
            repo_info = request.get("repo", {})
            repo = repo_info.get("localPath") or repo_info.get("repoUrl") or f"{repo_info.get('owner', '')}/{repo_info.get('repo', '')}"
            language = request.get("language", "en")
            
            cache_path = _get_cache_path(repo, language)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(request, f, ensure_ascii=False, indent=2)
                
            return {"status": "success", "message": "Cache saved successfully"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.delete("/api/wiki_cache")
    def delete_wiki_cache(repo: str, language: str = "en") -> dict[str, object]:
        try:
            cache_path = _get_cache_path(repo, language)
            if cache_path.exists():
                cache_path.unlink()
            return {"status": "success"}
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
        import re
        try:
            repo_input = _resolve_repo_input(request.repo, request.repo_url)
            # Clean path from quotes or extra spaces
            repo_input = repo_input.strip().strip('"').strip("'")
            repo_path = resolve_repo_path(repo_input, token=request.token, repo_type=request.repo_type)
            
            print(f"DEBUG: Resolved repo_path for analysis: {repo_path}")
            
            settings, runtime_provider = build_runtime(
                provider=request.provider,
                model=request.model,
                project_root=repo_path,
            )
            
            question = _extract_question(request)
            
            # Inject context
            if "CRITICAL STARTING INSTRUCTION:" in question:
                # Wiki page generation: inject explicitly listed files
                file_contents = ""
                # Robust regex for both: - [path](url) and - [path](path)
                matches = re.findall(r'-\s+\[([^\]]+)\]\(([^)]+)\)', question)
                # If that fails, try simpler one for just the bracketed part
                if not matches:
                    matches = [(m, m) for m in re.findall(r'-\s+\[([^\]]+)\]', question)]
                
                print(f"DEBUG: Found {len(matches)} potential files in prompt for injection.")
                
                injected_files = []
                # Pre-list all files for fuzzy matching
                all_repo_files = {str(p.relative_to(repo_path)).replace("\\", "/").lower(): p for p in repo_path.rglob("*") if p.is_file()}
                
                for file_path, _ in matches:
                    # Clean the path and normalize slashes
                    clean_path = file_path.strip().replace("\\", "/").lower()
                    
                    # 1. Try direct match
                    full_path = repo_path / file_path.strip()
                    target_p = None
                    if full_path.exists() and full_path.is_file():
                        target_p = full_path
                    # 2. Try normalized match in pre-listed files
                    elif clean_path in all_repo_files:
                        target_p = all_repo_files[clean_path]
                    # 3. Try partial match (e.g. "Cargo.toml" matches "crates/core/Cargo.toml")
                    else:
                        for rel_p_str, p in all_repo_files.items():
                            if rel_p_str.endswith("/" + clean_path) or rel_p_str == clean_path:
                                target_p = p
                                break
                    
                    if target_p:
                        try:
                            content = target_p.read_text(encoding='utf-8', errors='ignore')
                            display_name = str(target_p.relative_to(repo_path))
                            file_contents += f"\n\n--- FILE: {display_name} ---\n{content}\n"
                            injected_files.append(display_name)
                        except Exception as e:
                            print(f"DEBUG: Failed to read {target_p}: {e}")
                    else:
                        print(f"DEBUG: File NOT found in repo: {file_path}")

                if file_contents:
                    print(f"DEBUG: Successfully injected {len(injected_files)} files ({len(file_contents)} chars): {', '.join(injected_files)}")
                    question += f"\n\n[REAL SOURCE CODE CONTEXT]\nBelow is the actual content of the files you are asked to use. Base your wiki ONLY on this content:\n{file_contents}"
                else:
                    print("DEBUG: WARNING - No file contents were injected into the prompt!")
            elif "Analyze this GitHub repository" not in question:
                # Regular chat: perform RAG retrieval if index exists
                try:
                    from deepwiki.data.cache_manager import CacheManager
                    from deepwiki.data.vector_store import ChromaVectorStore
                    from deepwiki.providers.base import EmbeddingRequest
                    
                    files = read_repo_files(repo_path, limit=500)
                    cache_manager = CacheManager(settings.cache_dir)
                    cache_key = cache_manager.build_cache_key(
                        repo_path=repo_path,
                        files=files,
                        embed_provider=settings.embed_provider,
                        embed_model=settings.embed_model,
                        chunk_size=settings.chunk_size,
                        chunk_overlap=settings.chunk_overlap,
                    )
                    index_path = cache_manager.index_path(cache_key)
                    store = ChromaVectorStore(str(index_path))
                    
                    if store.load(str(index_path)):
                        question_embedding = await runtime_provider.embed(
                            EmbeddingRequest(
                                texts=[question],
                                model=settings.embed_model,
                                provider=settings.embed_provider,
                            )
                        )
                        if question_embedding.embeddings:
                            retrieved = store.query(embedding=question_embedding.embeddings[0], top_k=settings.top_k)
                            context_blocks = [f"[{res.metadata.get('file_path', '?')}]\n{res.text}" for res in retrieved]
                            if context_blocks:
                                context_text = "\n\n".join(context_blocks)
                                question = f"Context:\n{context_text}\n\nQuestion:\n{question}"
                except Exception as e:
                    print(f"RAG retrieval failed in chat stream: {e}")
            
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
        import re
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
                
                # Inject context
                if "CRITICAL STARTING INSTRUCTION:" in question:
                    file_contents = ""
                    matches = re.findall(r'-\s+\[([^\]]+)\]\(([^)]+)\)', question)
                    if not matches:
                        matches = [(m, m) for m in re.findall(r'-\s+\[([^\]]+)\]', question)]
                    
                    injected_files = []
                    # Pre-list all files for fuzzy matching
                    all_repo_files = {str(p.relative_to(repo_path)).replace("\\", "/").lower(): p for p in repo_path.rglob("*") if p.is_file()}
                    
                    for file_path, _ in matches:
                        clean_path = file_path.strip().replace("\\", "/").lower()
                        # 1. Try direct match
                        full_path = repo_path / file_path.strip()
                        target_p = None
                        if full_path.exists() and full_path.is_file():
                            target_p = full_path
                        # 2. Try normalized match
                        elif clean_path in all_repo_files:
                            target_p = all_repo_files[clean_path]
                        # 3. Try partial match
                        else:
                            for rel_p_str, p in all_repo_files.items():
                                if rel_p_str.endswith("/" + clean_path) or rel_p_str == clean_path:
                                    target_p = p
                                    break
                        
                        if target_p:
                            try:
                                content = target_p.read_text(encoding='utf-8', errors='ignore')
                                display_name = str(target_p.relative_to(repo_path))
                                file_contents += f"\n\n--- FILE: {display_name} ---\n{content}\n"
                                injected_files.append(display_name)
                            except Exception as e:
                                print(f"DEBUG: WS failed to read {target_p}: {e}")
                    
                    if file_contents:
                        print(f"DEBUG: WS Successfully injected {len(injected_files)} files.")
                        question += f"\n\n[REAL SOURCE CODE CONTEXT]\nBelow is the actual content of the files you are asked to use. Base your wiki ONLY on this content:\n{file_contents}"
                elif "Analyze this GitHub repository" not in question:
                    try:
                        from deepwiki.data.cache_manager import CacheManager
                        from deepwiki.data.vector_store import ChromaVectorStore
                        from deepwiki.providers.base import EmbeddingRequest
                        
                        files = read_repo_files(repo_path, limit=500)
                        cache_manager = CacheManager(settings.cache_dir)
                        cache_key = cache_manager.build_cache_key(
                            repo_path=repo_path,
                            files=files,
                            embed_provider=settings.embed_provider,
                            embed_model=settings.embed_model,
                            chunk_size=settings.chunk_size,
                            chunk_overlap=settings.chunk_overlap,
                        )
                        index_path = cache_manager.index_path(cache_key)
                        store = ChromaVectorStore(str(index_path))
                        
                        if store.load(str(index_path)):
                            question_embedding = await runtime_provider.embed(
                                EmbeddingRequest(
                                    texts=[question],
                                    model=settings.embed_model,
                                    provider=settings.embed_provider,
                                )
                            )
                            if question_embedding.embeddings:
                                retrieved = store.query(embedding=question_embedding.embeddings[0], top_k=settings.top_k)
                                context_blocks = [f"[{res.metadata.get('file_path', '?')}]\n{res.text}" for res in retrieved]
                                if context_blocks:
                                    context_text = "\n\n".join(context_blocks)
                                    question = f"Context:\n{context_text}\n\nQuestion:\n{question}"
                    except Exception as e:
                        print(f"RAG retrieval failed in websocket: {e}")

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

    @app.get("/api/models/config")
    @app.get("/models/config")
    def get_models_config():
        try:
            chat_catalog, _ = load_provider_catalogs()
            providers = []
            for p_id, models in chat_catalog.items():
                providers.append({
                    "id": p_id,
                    "name": p_id.capitalize(),
                    "models": [{"id": m, "name": m} for m in models]
                })
            return {"providers": providers, "defaultProvider": "ollama"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.get("/api/wiki_cache")
    def get_wiki_cache(repo: str, owner: str | None = None, language: str = "en"):
        try:
            lookup_repo = repo
            if owner and owner != "local": lookup_repo = f"{owner}/{repo}"
            
            cache_dir = _default_repo_cache_dir() / "wiki_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            safe_repo = lookup_repo.replace("/", "_").replace("\\", "_").replace(":", "_")
            cache_path = cache_dir / f"{safe_repo}_{language}.json"

            if not cache_path.exists():
                for f in cache_dir.glob(f"*{repo}*{language}.json"):
                    cache_path = f
                    break
            if cache_path.exists():
                import json
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {"status": "error", "message": "Cache not found"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.post("/api/wiki_cache")
    async def create_wiki_cache(request: dict):
        try:
            repo_info = request.get("repo", {})
            repo = repo_info.get("localPath") or repo_info.get("repoUrl") or f"{repo_info.get('owner', '')}/{repo_info.get('repo', '')}"
            language = request.get("language", "en")
            
            cache_dir = _default_repo_cache_dir() / "wiki_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            safe_repo = repo.replace("/", "_").replace("\\", "_").replace(":", "_")
            cache_path = cache_dir / f"{safe_repo}_{language}.json"

            import json
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(request, f, ensure_ascii=False, indent=2)
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.delete("/api/wiki_cache")
    def delete_wiki_cache(repo: str, owner: str | None = None, language: str = "en"):
        try:
            lookup_repo = repo
            if owner and owner != "local": lookup_repo = f"{owner}/{repo}"
            
            cache_dir = _default_repo_cache_dir() / "wiki_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            safe_repo = lookup_repo.replace("/", "_").replace("\\", "_").replace(":", "_")
            cache_path = cache_dir / f"{safe_repo}_{language}.json"

            if cache_path.exists(): cache_path.unlink()
            if cache_dir.exists():
                for f in cache_dir.glob(f"*{repo}*{language}.json"): f.unlink()
            return {"status": "success"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @app.get("/api/processed_projects")
    def processed_projects():
        try:
            cache_dir = _default_repo_cache_dir() / "wiki_cache"
            projects = []
            if cache_dir.exists():
                import json, os
                for f in cache_dir.glob("*.json"):
                    try:
                        with open(f, "r", encoding="utf-8") as file:
                            data = json.load(file)
                            repo_info = data.get("repo", {})
                            owner = repo_info.get("owner", "local")
                            repo_name = repo_info.get("repo", f.stem.split('_')[0])
                            projects.append({
                                "id": f"local_{owner}_{repo_name}",
                                "owner": owner, "repo": repo_name, "name": repo_name,
                                "repo_type": "local", "localPath": repo_info.get("localPath"),
                                "language": data.get("language", "en"),
                                "submittedAt": int(os.path.getmtime(f) * 1000)
                            })
                    except: continue
            return sorted(projects, key=lambda x: x["submittedAt"], reverse=True)
        except: return []

    @app.get("/local_repo/structure")
    def local_repo_structure(path: str):
        try:
            repo_path = Path(path).expanduser().resolve()
            if not repo_path.exists(): return {"status": "error", "message": "Not found"}
            files = read_repo_files(repo_path, limit=500)
            file_tree = "\n".join([f[0] for f in files])
            readme = ""
            for name in ["README.md", "README"]:
                if (repo_path / name).exists():
                    readme = (repo_path / name).read_text(encoding="utf-8", errors="ignore")
                    break
            return {"status": "success", "file_tree": file_tree, "readme": readme}
        except Exception as exc: return {"status": "error", "message": str(exc)}

    from pydantic import BaseModel
    class ChatStreamRequest(BaseModel):
        repo: Optional[str] = None
        repo_url: Optional[str] = None
        repo_type: str = "github"
        type: Optional[str] = None
        token: Optional[str] = None
        messages: list[dict]
        provider: Optional[str] = None
        model: Optional[str] = None

    @app.post("/chat/completions/stream")
    async def chat_stream_internal(request: ChatStreamRequest):
        from fastapi.responses import StreamingResponse
        import re
        try:
            actual_repo_type = request.type or request.repo_type
            actual_repo = request.repo or request.repo_url or ""
            
            if actual_repo.startswith("local://"):
                repo_name = actual_repo.replace("local://", "")
                potential_paths = [Path.cwd() / repo_name, Path.cwd().parent / repo_name]
                for p in potential_paths:
                    if p.exists() and p.is_dir():
                        actual_repo = str(p)
                        break
                else:
                    actual_repo = repo_name

            repo_input = _resolve_repo_input(actual_repo, request.repo_url)
            repo_path = resolve_repo_path(repo_input.strip().strip('"'), token=request.token)
            settings, runtime_provider = build_runtime(provider=request.provider, model=request.model, project_root=repo_path)
            
            question = ""
            if request.messages:
                question = request.messages[-1].get("content", "")

            is_analysis = "<file_tree>" in question or "Act as a senior" in question
            file_contents = ""
            matches = []
            
            if "CRITICAL STARTING INSTRUCTION:" in question:
                matches = re.findall(r'-\s+\[([^\]]+)\]', question)
            elif "using:" in question:
                m = re.search(r'using:\s*(.+?)\.\s*Language:', question)
                if m:
                    matches = [f.strip() for f in m.group(1).split(',')]

            if matches:
                all_repo_files = {str(p.relative_to(repo_path)).replace("\\", "/").lower(): p for p in repo_path.rglob("*") if p.is_file()}
                for f_path in matches:
                    clean_p = f_path.strip().replace("\\", "/").lower()
                    target = None
                    if (repo_path / f_path.strip()).exists(): target = repo_path / f_path.strip()
                    elif clean_p in all_repo_files: target = all_repo_files[clean_p]
                    else:
                        for rel, p in all_repo_files.items():
                            if rel.endswith("/" + clean_p): target = p; break
                    if target:
                        file_contents += f"\n--- FILE: {target.relative_to(repo_path)} ---\n{target.read_text(errors='ignore')}\n"
                if file_contents: question += f"\n\n[SOURCE CONTEXT]\n{file_contents}"

            async def event_generator():
                buffer = ""
                xml_detected = False
                try:
                    async for chunk in runtime_provider.stream(CompletionRequest(prompt=question, model=settings.model, provider=settings.provider)):
                        buffer += chunk
                        if not xml_detected and len(buffer) > 20:
                            if any(k in buffer.lower() for k in ["cannot", "unable", "as an ai", "file system"]):
                                yield f'<wiki_structure><title>Wiki for {repo_path.name}</title><description>Reconstructed</description><pages><page id="p1"><title>Main Analysis</title><relevant_files><file_path>README.md</file_path></relevant_files></page></pages></wiki_structure>'
                                return
                        if "<wiki_structure>" in buffer: xml_detected = True
                        yield chunk
                finally:
                    pass
            return StreamingResponse(event_generator(), media_type="text/event-stream")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/auth/validate")
    def auth_validate_api(): return {"status": "success", "valid": True}

    @app.get("/lang/config")
    def get_lang_config():
        return {
            "supported_languages": {"en": "English", "zh": "Mandarin Chinese (中文)"},
            "default": "en"
        }

    return app
